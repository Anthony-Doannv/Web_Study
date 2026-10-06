import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug chỉ bật khi đặt FLASK_DEBUG=1 trong .env (không bao giờ bật khi deploy)
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
