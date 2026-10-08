import json
import aiosqlite
from aiohttp import web
from datetime import datetime, timezone


DATABASE = "ads.db"
routes = web.RouteTableDef()


def get_current_time():
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row):
    if row is None:
        return None

    return dict(row)


async def get_json(request):
    if request.content_type != "application/json":
        return None

    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    return data


def validate_required_fields(data):
    required_fields = ("title", "description", "owner")
    missing_fields = [field for field in required_fields if (field not in data or not isinstance(data[field], str) or not data[field].strip())]

    return missing_fields


async def init_database(app):
    async with aiosqlite.connect(DATABASE) as database:
        await database.execute("PRAGMA journal_mode=WAL")

        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                owner TEXT NOT NULL
            )
            """
        )

        await database.commit()


@routes.get("/ads")
async def get_ads(request):
    async with aiosqlite.connect(DATABASE) as database:
        database.row_factory = aiosqlite.Row

        async with database.execute(
                """
                SELECT id, title, description, created_at, owner
                FROM ads
                ORDER BY id
                """
        ) as cursor:
            rows = await cursor.fetchall()

    return web.json_response([
        row_to_dict(row)
        for row in rows
    ])


@routes.get(r"/ads/{ad_id:\d+}")
async def get_ad(request):
    ad_id = int(request.match_info["ad_id"])

    async with aiosqlite.connect(DATABASE) as database:
        database.row_factory = aiosqlite.Row

        async with database.execute(
                """
                SELECT id, title, description, created_at, owner
                FROM ads
                WHERE id = ?
                """,
                (ad_id,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return web.json_response({"error": "Объявление не найдено"}, status=404)

    return web.json_response(row_to_dict(row))


@routes.post("/ads")
async def create_ad(request):
    data = await get_json(request)

    if data is None:
        return web.json_response(
            {"error": ("Тело запроса должно содержать корректный JSON с Content-Type: application/json")}, status=400)

    missing_fields = validate_required_fields(data)

    if missing_fields:
        return web.json_response({"error": "Не заполнены обязательные поля", "fields": missing_fields}, status=400)

    title = data["title"].strip()
    description = data["description"].strip()
    owner = data["owner"].strip()
    created_at = get_current_time()

    async with aiosqlite.connect(DATABASE) as database:
        database.row_factory = aiosqlite.Row

        cursor = await database.execute(
            """
            INSERT INTO ads (
                title,
                description,
                created_at,
                owner
            )
            VALUES (?, ?, ?, ?)
            """,
            (title, description, created_at, owner)
        )

        await database.commit()

        ad_id = cursor.lastrowid
        await cursor.close()

        async with database.execute(
                """
                SELECT id, title, description, created_at, owner
                FROM ads
                WHERE id = ?
                """,
                (ad_id,)
        ) as cursor:
            created_ad = await cursor.fetchone()

    return web.json_response(
        row_to_dict(created_ad),
        status=201
    )


@routes.put(r"/ads/{ad_id:\d+}")
@routes.patch(r"/ads/{ad_id:\d+}")
async def update_ad(request):
    ad_id = int(request.match_info["ad_id"])
    data = await get_json(request)

    if data is None:
        return web.json_response({"error": ("Тело запроса должно содержать корректный JSON с Content-Type: application/json")},status=400)

    editable_fields = ("title", "description", "owner")

    if request.method == "PUT":
        missing_fields = validate_required_fields(data)

        if missing_fields:
            return web.json_response({"error": "Не заполнены обязательные поля", "fields": missing_fields}, status=400)

    unknown_fields = [field for field in data if field not in editable_fields]
    if unknown_fields:
        return web.json_response({"error": "Обнаружены неизвестные поля", "fields": unknown_fields},status=400)

    update_values = {}
    for field in editable_fields:
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip():
                return web.json_response({"error": (f"Поле '{field}' должно быть непустой строкой")}, status=400)
            update_values[field] = value.strip()

    if not update_values:
        return web.json_response({"error": "Не указаны поля для изменения"}, status=400)

    async with aiosqlite.connect(DATABASE) as database:
        database.row_factory = aiosqlite.Row

        async with database.execute("SELECT id FROM ads WHERE id = ?", (ad_id,)) as cursor:
            existing_ad = await cursor.fetchone()

        if existing_ad is None:
            return web.json_response({"error": "Объявление не найдено"}, status=404)

        set_expression = ", ".join(f"{field} = ?" for field in update_values)

        parameters = [*update_values.values(), ad_id]

        await database.execute(
            f"""
            UPDATE ads
            SET {set_expression}
            WHERE id = ?
            """,
            parameters
        )

        await database.commit()

        async with database.execute(
                """
                SELECT id, title, description, created_at, owner
                FROM ads
                WHERE id = ?
                """,
                (ad_id,)
        ) as cursor:
            updated_ad = await cursor.fetchone()

    return web.json_response(row_to_dict(updated_ad))


@routes.delete(r"/ads/{ad_id:\d+}")
async def delete_ad(request):
    ad_id = int(request.match_info["ad_id"])

    async with aiosqlite.connect(DATABASE) as database:
        cursor = await database.execute(
            "DELETE FROM ads WHERE id = ?",
            (ad_id,)
        )

        await database.commit()

        deleted_count = cursor.rowcount
        await cursor.close()

    if deleted_count == 0:
        return web.json_response({"error": "Объявление не найдено"}, status=404)

    return web.Response(status=204)


def create_app():
    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(init_database)
    return app


if __name__ == "__main__":
    web.run_app(
        create_app(),
        host="127.0.0.1",
        port=8080
    )