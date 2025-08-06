# server/routes.py
from flask import (
    Flask, request, render_template, jsonify, redirect, url_for, flash
)
from extensions import db
from models import Device, Software, Blacklist, AdminPassword
from datetime import datetime, timedelta  # 这里补上timedelta导入
from sqlalchemy import and_, func
from sqlalchemy.orm import aliased

def register_routes(app):
    @app.route('/')
    def dashboard():
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # 子查询：每个 mac_address 当天最新扫描时间
        subq = db.session.query(
            Device.mac_address,
            func.max(Device.last_scan).label('max_scan')
        ).filter(
            and_(Device.last_scan >= today_start, Device.last_scan < today_end)
        ).group_by(Device.mac_address).subquery()

        DeviceAlias = aliased(Device)

        latest_devices = db.session.query(DeviceAlias).join(
            subq,
            and_(
                DeviceAlias.mac_address == subq.c.mac_address,
                DeviceAlias.last_scan == subq.c.max_scan
            )
        ).all()

        black_keywords = [b.keyword.lower() for b in Blacklist.query.all()]

        violations = []
        for d in latest_devices:
            for s in d.softwares:
                for k in black_keywords:
                    if k in s.name.lower():
                        violations.append({
                            'username': d.username,
                            'hostname': d.hostname,
                            'mac': d.mac_address,
                            'software': s.name
                        })

        return render_template('dashboard.html', devices=latest_devices, violations=violations)

    @app.route('/upload', methods=['POST'])
    def upload():
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求体不能为空'}), 400

        username = data.get('username')
        hostname = data.get('hostname')
        macs = data.get('macs', [])
        softwares = data.get('softwares', [])

        if not username or not hostname or not macs or not softwares:
            return jsonify({'error': '缺少必要字段'}), 400

        for mac in macs:
            device = Device.query.filter_by(mac_address=mac).first()
            if not device:
                device = Device(username=username, hostname=hostname, mac_address=mac, last_scan=datetime.utcnow())
                db.session.add(device)
                db.session.commit()
            else:
                device.username = username
                device.hostname = hostname
                device.last_scan = datetime.utcnow()
                db.session.commit()
                # 删除旧软件列表，避免重复
                Software.query.filter_by(device_id=device.id).delete()
                db.session.commit()

            for sw in softwares:
                s = Software(device_id=device.id, name=sw.get('name', ''), version=sw.get('version', ''))
                db.session.add(s)
            db.session.commit()

        return jsonify({'status': 'success'})


    @app.route('/admin/password', methods=['GET', 'POST'])
    def admin_password_page():
        admin_pw = AdminPassword.query.first()
        if request.method == 'POST':
            pw = request.form.get('password', '').strip()
            if not pw:
                flash('密码不能为空', 'danger')
            else:
                if admin_pw:
                    admin_pw.password = pw
                else:
                    admin_pw = AdminPassword(password=pw)
                    db.session.add(admin_pw)
                db.session.commit()
                flash('管理员密码设置成功', 'success')
            return redirect(url_for('admin_password_page'))

        return render_template('admin_password.html', password=admin_pw.password if admin_pw else '')

    @app.route('/blacklist', methods=['GET', 'POST'])
    def blacklist_page():
        page = request.args.get('page', 1, type=int)
        per_page = 10

        if request.method == 'POST':
            raw_text = request.form.get('keywords', '').strip()
            if not raw_text:
                flash('输入不能为空', 'danger')
                return redirect(url_for('blacklist_page'))

            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            added_count = 0
            for keyword in lines:
                exists = Blacklist.query.filter(func.lower(Blacklist.keyword) == keyword.lower()).first()
                if not exists:
                    db.session.add(Blacklist(keyword=keyword))
                    added_count += 1
            db.session.commit()
            flash(f'成功添加 {added_count} 条关键字', 'success')
            return redirect(url_for('blacklist_page'))

        pagination = Blacklist.query.order_by(Blacklist.id.desc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        return render_template('blacklist.html', pagination=pagination, keywords=pagination.items)

    @app.route('/blacklist/edit/<int:bid>', methods=['POST'])
    def blacklist_edit(bid):
        new_keyword = request.form.get('keyword', '').strip()
        if not new_keyword:
            flash('关键字不能为空', 'danger')
            return redirect(url_for('blacklist_page'))

        existing = Blacklist.query.filter(func.lower(Blacklist.keyword) == new_keyword.lower(), Blacklist.id != bid).first()
        if existing:
            flash('该关键字已存在', 'warning')
            return redirect(url_for('blacklist_page'))

        item = Blacklist.query.get_or_404(bid)
        item.keyword = new_keyword
        db.session.commit()
        flash('关键字修改成功', 'success')
        return redirect(url_for('blacklist_page'))

    @app.route('/blacklist/delete/<int:bid>', methods=['POST'])
    def blacklist_delete(bid):
        Blacklist.query.filter_by(id=bid).delete()
        db.session.commit()
        flash('删除成功', 'success')
        return redirect(url_for('blacklist_page'))

    @app.route('/blacklist/delete_batch', methods=['POST'])
    def blacklist_delete_batch():
        ids = request.form.getlist('delete_ids')
        if not ids:
            flash('未选择任何关键字', 'warning')
            return redirect(url_for('blacklist_page'))

        Blacklist.query.filter(Blacklist.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        flash(f'成功批量删除 {len(ids)} 条关键字', 'success')
        return redirect(url_for('blacklist_page'))

