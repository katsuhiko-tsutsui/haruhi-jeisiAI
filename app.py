import os
from flask import Flask
from main.routes import main_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "haruhi-dev-secret-2025")
    app.register_blueprint(main_bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False)


