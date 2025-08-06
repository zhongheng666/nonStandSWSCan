from flask import (
    request, render_template, jsonify, redirect, url_for, flash
)
from extensions import db
from models import Device, Software, Blacklist, AdminPassword
from datetime import datetime, timedelta, date, time
from sqlalchemy import and_, func
from collections import defaultdict
from sqlalchemy.orm import joinedload


def register_routes(app):

    @app.route('/')
    def dashboard():
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)

        # 预加载软件，避免懒加载空白
        today_devices = Device.query.options(joinedload(Device.softwares)).filter(
            and_(Device.last_scan >= today_start, Device.last_scan < today_end)
        ).order_by(Device.last_scan.desc()).all()

        # 合并同主机 + 员工名下的多个 MAC 地址
        devices_map = defaultdict(lambda: {
            "hostname": "",
            "username": "",
            "mac_addresses": set(),
            "last_scan": None,
            "softwares": []
        })

        for d in today_devices:
            key = (d.hostname, d.username)
            entry = devices_map[key]
            entry["hostname"] = d.hostname
            entry["username"] = d.username
            entry["mac_addresses"].add(d.mac_address)
            if entry["last_scan"] is None or d.last_scan > entry["last_scan"]:
                entry["last_scan"] = d.last_scan
                entry["softwares"] = d.softwares

        merged_devices = []
        black_keywords = [b.keyword.lower() for b in Blacklist.query.all()]
        violations = []

        for entry in devices_map.values():
            merged_devices.append({
                "hostname": entry["hostname"],
                "username": entry["username"],
                "mac_addresses": ", ".join(sorted(entry["mac_addresses"])),
                "last_scan": entry["last_scan"],
                "softwares": entry["softwares"]
            })

            for sw in entry["softwares"]:
                for k in black_keywords:
                    if k in sw.name.lower():
                        violations.append({
                            'username': entry["username"],
                            'hostname': entry["hostname"],
                            'mac': ", ".join(sorted(entry["mac_addresses"])),
                            'software': sw.name
                        })

        return render_template('dashboard.html', devices=merged_devices, violations=violations)

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
                db.session.flush()  # 获得 device.id
            else:
                device.username = username
                device.hostname = hostname
                device.last_scan = datetime.utcnow()
                # 删除旧软件
                Software.query.filter_by(device_id=device.id).delete()

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

