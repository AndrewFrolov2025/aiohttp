import json
from aiohttp import web
from datetime import datetime, timezone

ads = {}
next_ad_id = 1
routes = web.RouteTableDef()

def get_current_time():
    return datetime.now(timezone.utc).isoformat()

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

def validate_ad_data(data):
    required_fields = ['title', 'description', 'owner']

    missing_fields = [filed for filed in required_fields if not isinstance(data.get(filed), str) or not data [filed].strip()]
    if missing_fields:
        return {'error': 'Не все поля заполнены', 'fields': missing_fields}

    return None


@routes.get("/ads")
async def get_ads(request):
    return web.json_response(list(ads.values()))

@routes.get(r"/ads/{ad_id:\d+}")
async def get_ad(request):
    ad_id = int(request.match_info["ad_id"])
    ad = ads.get(ad_id)

    if ad is None:
        return web.json_response(
            {"error": "Объявление не найдено"},
            status=404
        )

    return web.json_response(ad)

@routes.post("/ads")
async def create_ad(request):
    global next_ad_id

    data = await get_json(request)

    if data is None:
        return web.json_response({"error": ("Тело запроса должно содержать корректный JSON с Content-Type: application/json")},status=400)

    validation_error = validate_ad_data(data)

    if validation_error:
        return web.json_response(validation_error, status=400)

    ad = {"id": next_ad_id, "title": data["title"].strip(), "description": data["description"].strip(), "created_at": get_current_time(), "owner": data["owner"].strip()}
    ads[next_ad_id] = ad
    next_ad_id += 1
    return web.json_response(ad, status=201)

@routes.put(r"/ads/{ad_id:\d+}")
@routes.patch(r"/ads/{ad_id:\d+}")
async def update_ad(request):
    ad_id = int(request.match_info["ad_id"])
    ad = ads.get(ad_id)

    if ad is None:
        return web.json_response({"error": "Объявление не найдено"},status=404)
    data = await get_json(request)
    if data is None:
        return web.json_response(
            {"error": ("Тело запроса должно содержать корректный JSON с Content-Type: application/json")},status=400)
    editable_fields = ["title", "description", "owner"]
    for field in editable_fields:
        if field in data:
            if not isinstance(data[field], str) or not data[field].strip():
                return web.json_response({"error": f"Поле '{field}' не может быть пустым"},status=400)

            ad[field] = data[field].strip()

    return web.json_response(ad)

@routes.delete(r"/ads/{ad_id:\d+}")
async def delete_ad(request):
    ad_id = int(request.match_info["ad_id"])
    deleted_ad = ads.pop(ad_id, None)

    if deleted_ad is None:
        return web.json_response({"error": "Объявление не найдено"},status=404)
    return web.json_response({"message": "Объявление удалено","ad": deleted_ad})

app = web.Application()
app.add_routes(routes)

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=8080)