from flask import Flask, render_template
from flask_cors import CORS
from flask_pymongo import PyMongo
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os


app = Flask(__name__)
CORS(app)


def _load_env_file(env_path: str = ".env") -> None:
    """Load .env values into process env if they are not already set."""
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value



_load_env_file()

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallback-secret-key")
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "")
mongo = PyMongo(app)

MONGO_DB = os.getenv("MONGO_DB")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION")

SENSOR_MAP = {
    "1": "Duży Pokój",
    "2": "Sypialnia Mama",
    "3": "Góra Dziubek",
    "4": "Sypialnia Dziubków",
}


def _to_cet(dt: datetime | None) -> str | None:
    if dt is None:
        return None

    # Treat naive datetimes as UTC to match stored Mongo timestamps.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S %Z")


@app.route("/", methods=("GET", "POST"))
def home():
    records = []
    error_message = None

    if not (app.config["MONGO_URI"] and MONGO_DB and MONGO_COLLECTION):
        error_message = "MongoDB configuration is missing. Check MONGO_URI, MONGO_DB and MONGO_COLLECTION."
    else:
        try:
            collection = mongo.cx[MONGO_DB][MONGO_COLLECTION]

            now_utc = datetime.now(timezone.utc)
            one_hour_ago = now_utc - timedelta(hours=1)

            cursor = collection.find(
                {"updated_at": {"$gte": one_hour_ago}},
                {"_id": 0, "bucket": 1, "updated_at": 1, "sensors": 1},
            ).sort("updated_at", -1)

            for doc in cursor:
                sensors = []
                for sensor in doc.get("sensors", []):
                    sensor_id = str(sensor.get("sensor_name", ""))
                    sensors.append(
                        {
                            **sensor,
                            "sensor_name": SENSOR_MAP.get(sensor_id, sensor_id),
                        }
                    )

                records.append(
                    {
                        "bucket_cet": _to_cet(doc.get("bucket")),
                        "updated_at_cet": _to_cet(doc.get("updated_at")),
                        "sensors": sensors,
                    }
                )
        except Exception as exc:
            error_message = f"MongoDB query failed: {exc}"

    return render_template("home.html", records=records, error_message=error_message)


if __name__ == "__main__":
    app.run(debug=True)
