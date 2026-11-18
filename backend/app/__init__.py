"""Flask application factory with Blueprint registration."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before importing config, since Config reads os.environ at import time.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask  # noqa: E402
from flask_cors import CORS  # noqa: E402
from flask_jwt_extended import JWTManager  # noqa: E402
from flask_migrate import Migrate  # noqa: E402
from flask_sqlalchemy import SQLAlchemy  # noqa: E402

from app.config import config_by_name  # noqa: E402

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app(config_name: str = "default") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # CORS — credentials required for httpOnly cookie auth
    CORS(
        app,
        origins=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(","),
        supports_credentials=True,
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # Blueprints (routes wired in later phases)
    from app.routes.auth import auth_bp
    from app.routes.ai_tutor import ai_tutor_bp
    from app.routes.quizzes import quizzes_bp
    from app.routes.flashcards import flashcards_bp
    from app.routes.analytics import analytics_bp
    from app.routes.uploads import uploads_bp
    from app.routes.lessons import lessons_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(ai_tutor_bp, url_prefix="/api/chat")
    app.register_blueprint(quizzes_bp, url_prefix="/api/quiz")
    app.register_blueprint(flashcards_bp, url_prefix="/api/flashcards")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(uploads_bp, url_prefix="/api/uploads")
    app.register_blueprint(lessons_bp, url_prefix="/api/lessons")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")

    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "EduTrack AI"}

    @app.errorhandler(413)
    def request_too_large(_err):
        return {"error": "檔案太大（每個上限 10MB）"}, 413

    return app
