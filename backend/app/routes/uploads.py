"""Personal note uploads. Every query is scoped to the logged-in student."""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.chroma_store import init_chroma_store
from app.services.user_library import LibraryError, LibraryService, quota_payload

uploads_bp = Blueprint("uploads", __name__)


def _get_store():
    return init_chroma_store(current_app.config)


def _service() -> LibraryService:
    return LibraryService(_get_store(), current_app.config["UPLOAD_DIR"])


def _user_id() -> int:
    return int(get_jwt_identity())


def _read_upload() -> bytes:
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise LibraryError("請選擇一個 PDF、TXT 或 MD 檔案")
    # Read one byte past the per-file cap so the quota check can reject it.
    from app.services.user_library import MAX_FILE_BYTES

    data = uploaded.stream.read(MAX_FILE_BYTES + 1)
    if not data:
        raise LibraryError("檔案是空的")
    return data


@uploads_bp.route("", methods=["GET"])
@jwt_required()
def list_uploads():
    service = _service()
    documents = service.list_documents(_user_id())
    return jsonify(
        {
            "documents": [doc.to_dict() for doc in documents],
            "quota": quota_payload(documents),
        }
    )


@uploads_bp.route("", methods=["POST"])
@jwt_required()
def create_upload():
    uploaded = request.files.get("file")
    filename = uploaded.filename if uploaded is not None else None
    try:
        data = _read_upload()
        doc = _service().save_upload(
            user_id=_user_id(),
            filename=filename,
            subject=request.form.get("subject"),
            data=data,
        )
    except LibraryError as exc:
        return jsonify({"error": exc.message}), exc.status
    return jsonify({"document": doc.to_dict()}), 201


@uploads_bp.route("/<int:document_id>", methods=["DELETE"])
@jwt_required()
def delete_upload(document_id: int):
    try:
        deleted = _service().delete_document(_user_id(), document_id)
    except LibraryError as exc:
        return jsonify({"error": exc.message}), exc.status
    except Exception:
        current_app.logger.exception("failed to delete upload %s", document_id)
        return jsonify({"error": "未能刪除檔案，請稍後再試"}), 502
    if not deleted:
        return jsonify({"error": "找不到這個檔案"}), 404
    return jsonify({"message": "deleted"})
