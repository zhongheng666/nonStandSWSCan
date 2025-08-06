# server/app.py
from flask import Flask
from extensions import db
from routes import register_routes
import models  # 导入模型，确保 create_all 生效

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 必须设置，保证 session 和 flash 正常
app.secret_key = 'dev_secret_key_please_change_me_123456'

db.init_app(app)

with app.app_context():
    db.create_all()

register_routes(app)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8888)

