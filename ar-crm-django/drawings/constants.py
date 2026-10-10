"""Which files may be uploaded, and which can be shown inside the browser."""

# Approved list: anything not here is rejected.
ALLOWED_EXTENSIONS = {
    # drawings and models
    "dwg", "dxf", "skp", "rvt", "rfa", "ifc", "3dm", "dgn",
    # documents and images
    "pdf", "png", "jpg", "jpeg", "webp",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    # bundles
    "zip",
}

# These open directly in the browser (good for phones). Everything else downloads.
PREVIEW_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

DEFAULT_MAX_UPLOAD_MB = 100
