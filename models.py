from extensions import db
from datetime import datetime

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(128), nullable=False)  # 员工名
    mac_address = db.Column(db.String(64), nullable=False)
    last_scan = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 设备关联的软件列表
    softwares = db.relationship('Software', backref='device', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Device {self.hostname} ({self.mac_address})>'


class Software(db.Model):
    __tablename__ = 'softwares'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    version = db.Column(db.String(64))

    def __repr__(self):
        return f'<Software {self.name} v{self.version}>'


class Blacklist(db.Model):
    __tablename__ = 'blacklists'

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(128), unique=True, nullable=False)

    def __repr__(self):
        return f'<Blacklist {self.keyword}>'


class AdminPassword(db.Model):
    __tablename__ = 'adminpasswords'

    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(256), nullable=False)  # 存储加密后密码更安全

    def __repr__(self):
        return '<AdminPassword [hidden]>'

