# server/models.py
from extensions import db
from datetime import datetime

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64))
    hostname = db.Column(db.String(128))
    mac_address = db.Column(db.String(128))
    last_scan = db.Column(db.DateTime, default=datetime.utcnow)
    softwares = db.relationship('Software', backref='device', lazy=True)

class Software(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    name = db.Column(db.String(256))
    version = db.Column(db.String(64))

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(128), unique=True)

class AdminPassword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(128))

