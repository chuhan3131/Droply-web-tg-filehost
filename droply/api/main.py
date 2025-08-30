from fastapi import FastAPI, Request, HTTPException, UploadFile, File as FastFile, Form, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import Optional, List
import os
import shutil
import urllib.parse
import uuid
import shortuuid
from datetime import datetime, timedelta
import asyncio
import csv
import io
import aiohttp

from aiogram import Bot
from bot.config import BOT_TOKEN, ADMIN_IDS, BASE_URL
from .database import get_db
from .models import File, FileAccess

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = Bot(token=BOT_TOKEN)

os.makedirs("api/files", exist_ok=True)
os.makedirs("api/templates", exist_ok=True)

app = FastAPI(title="Droply", version="1.3.0")

app.mount("/files", StaticFiles(directory="api/files"), name="files")
templates = Jinja2Templates(directory="api/templates")


# ================== УТИЛИТЫ ==================
def generate_short_code() -> str:
    return shortuuid.ShortUUID().random(length=5)

def _get_client_ip(req: Request) -> str:
    xfwd = req.headers.get("x-forwarded-for")
    if xfwd:
        return xfwd.split(",")[0].strip()
    return req.client.host

async def geo_lookup(ip: str) -> tuple[str, str]:
    try:
        url = f"http://ip-api.com/json/{ip}?lang=ru&fields=status,country,city"
        timeout = aiohttp.ClientTimeout(total=2.5)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as r:
                data = await r.json()
                if data.get("status") == "success":
                    return data.get("country") or "", data.get("city") or ""
    except Exception:
        pass
    return "", ""

async def notify_owner(file: File, event: str, ip: str, ua: str, country: str, city: str):
    if not file.user_id:
        return
    if event == "visit" and not file.notify_visits:
        return
    if event == "download" and not file.notify_downloads:
        return

    place = f"{country}, {city}".strip(", ").strip()
    place_txt = f" 🌍 {place}" if place else ""
    fileee = urllib.parse.unquote(file.original_filename)
    msg = (
        f"🔔 <b>{'Просмотр страницы' if event=='visit' else 'Скачивание файла'}\n\n"
        f"📁 {fileee}\n"
        f"🔗 <code>{BASE_URL}/{file.file_code}</code>\n"
        f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"🌐 IP: <code>{ip}</code>{place_txt}</b>\n"
    )
    try:
        await bot.send_message(chat_id=file.user_id, text=msg, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass

async def write_access(db: Session, file_code: str, access_type: str, ip: str, ua: str):
    country, city = await geo_lookup(ip)
    access = FileAccess(
        file_code=file_code,
        access_type=access_type,
        ip_address=ip,
        user_agent=ua or "",
        access_time=datetime.now(),
        country=country,
        city=city
    )
    db.add(access)
    db.commit()
    return country, city


# ================== ПУБЛИЧНЫЕ РОУТЫ ==================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Droply — convenient file sharing service",
            "bot_link": "https://t.me/juu3tt8t8bot"
        }
    )


@app.get("/{file_code}", response_class=HTMLResponse)
async def short_link(file_code: str, request: Request, db: Session = Depends(get_db)):
    file = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="Файл не найден")

    ip = _get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    try:
        country, city = await write_access(db, file_code, "visit", ip, ua)
        asyncio.create_task(notify_owner(file, "visit", ip, ua, country, city))
    except Exception:
        pass

    return templates.TemplateResponse("download.html", {"request": request, "file": file})

@app.get("/download/{file_code}")
async def download_file(request: Request, file_code: str, db: Session = Depends(get_db)):
    file = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="Файл не найден")

    file_path = f"api/files/{file.stored_filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден на сервере")

    ip = _get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    try:
        country, city = await write_access(db, file_code, "download", ip, ua)
        asyncio.create_task(notify_owner(file, "download", ip, ua, country, city))
    except Exception:
        pass

    filename = file.original_filename
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"
    }

    return FileResponse(path=file_path, filename=filename, headers=headers, media_type="application/octet-stream")


@app.post("/api/upload")
async def upload_file(file: UploadFile, user_id: Optional[int] = Form(default=None), db: Session = Depends(get_db)):
    try:
        file_code = generate_short_code()
        ext = os.path.splitext(file.filename)[1] if file.filename else ""
        stored_filename = f"{uuid.uuid4()}{ext}"
        file_path = f"api/files/{stored_filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(file_path)

        file_obj = File(
            file_code=file_code,
            original_filename=file.filename or stored_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            user_id=user_id,
            upload_date=datetime.now(),
            notify_visits=True,
            notify_downloads=True
        )
        db.add(file_obj)
        db.commit()
        db.refresh(file_obj)

        return JSONResponse({
            "success": True,
            "file_code": file_code,
            "filename": file_obj.original_filename,
            "size": file_size,
            "download_url": f"{BASE_URL}/{file_code}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/{file_code}")
async def get_file_stats(file_code: str, db: Session = Depends(get_db)):
    file = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    visits = db.query(FileAccess).filter(FileAccess.file_code == file_code, FileAccess.access_type == "visit").count()
    downloads = db.query(FileAccess).filter(FileAccess.file_code == file_code, FileAccess.access_type == "download").count()

    recent_activity = db.query(FileAccess).filter(FileAccess.file_code == file_code)\
        .order_by(FileAccess.access_time.desc()).limit(10).all()

    return {
        "file_code": file_code,
        "filename": file.original_filename,
        "size": file.file_size,
        "visits": visits,
        "downloads": downloads,
        "notify_visits": file.notify_visits,
        "notify_downloads": file.notify_downloads,
        "recent_activity": [
            {
                "access_type": a.access_type,
                "ip_address": a.ip_address,
                "user_agent": a.user_agent,
                "country": a.country,
                "city": a.city,
                "access_time": a.access_time
            }
            for a in recent_activity
        ]
    }

@app.get("/api/files/{user_id}")
async def get_user_files(user_id: int, db: Session = Depends(get_db)):
    user_files = db.query(File).filter(File.user_id == user_id, File.is_active == True).order_by(desc(File.upload_date)).all()
    return {"files": [
        {
            "file_code": f.file_code,
            "filename": f.original_filename,
            "size": f.file_size,
            "upload_date": f.upload_date.isoformat(),
            "notify_visits": f.notify_visits,
            "notify_downloads": f.notify_downloads,
            "download_url": f"{BASE_URL}/{f.file_code}"
        } for f in user_files
    ]}

@app.delete("/api/files/{file_code}")
async def delete_file(file_code: str, user_id: int = Form(...), db: Session = Depends(get_db)):
    file = db.query(File).filter(File.file_code == file_code).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    path = f"api/files/{file.stored_filename}"
    if os.path.exists(path):
        os.remove(path)
    file.is_active = False
    db.commit()
    return {"success": True, "message": "File deleted"}

@app.patch("/api/files/{file_code}/notify_visits")
async def toggle_visit_notifications(file_code: str, user_id: int = Form(...), db: Session = Depends(get_db)):
    file = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    file.notify_visits = not file.notify_visits
    db.commit()
    return {"success": True, "notify_visits": file.notify_visits}

@app.patch("/api/files/{file_code}/notify_downloads")
async def toggle_download_notifications(file_code: str, user_id: int = Form(...), db: Session = Depends(get_db)):
    file = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    file.notify_downloads = not file.notify_downloads
    db.commit()
    return {"success": True, "notify_downloads": file.notify_downloads}

@app.put("/api/files/{file_code}/replace")
async def replace_file(file_code: str, file: UploadFile, user_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        file_obj = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
        if not file_obj:
            raise HTTPException(status_code=404, detail="File not found")
        if file_obj.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        old_path = f"api/files/{file_obj.stored_filename}"
        if os.path.exists(old_path):
            os.remove(old_path)

        ext = os.path.splitext(file.filename)[1] if file.filename else ""
        stored_filename = f"{uuid.uuid4()}{ext}"
        new_path = f"api/files/{stored_filename}"
        with open(new_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(new_path)
        file_obj.original_filename = file.filename or stored_filename
        file_obj.stored_filename = stored_filename
        file_obj.file_size = file_size
        file_obj.upload_date = datetime.now()
        db.commit()

        return JSONResponse({
            "success": True,
            "file_code": file_code,
            "filename": file_obj.original_filename,
            "size": file_size,
            "download_url": f"{BASE_URL}/{file_code}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



def _check_admin(admin_id: int):
    if admin_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Access denied")

@app.get("/api/admin/stats")
async def admin_stats(admin_id: int = Query(...), db: Session = Depends(get_db)):
    _check_admin(admin_id)

    total_files = db.query(File).filter(File.is_active == True).count()
    total_size = db.query(func.sum(File.file_size)).filter(File.is_active == True).scalar() or 0
    total_visits = db.query(FileAccess).filter(FileAccess.access_type == "visit").count()
    total_downloads = db.query(FileAccess).filter(FileAccess.access_type == "download").count()

    week_ago = datetime.now() - timedelta(days=7)
    files_this_week = db.query(File).filter(File.is_active == True, File.upload_date >= week_ago).count()
    visits_this_week = db.query(FileAccess).filter(FileAccess.access_type == "visit", FileAccess.access_time >= week_ago).count()
    downloads_this_week = db.query(FileAccess).filter(FileAccess.access_type == "download", FileAccess.access_time >= week_ago).count()

    top_files = db.query(
        File.file_code,
        File.original_filename,
        File.file_size,
        func.count(FileAccess.id).label('downloads')
    ).join(FileAccess, File.file_code == FileAccess.file_code)\
     .filter(File.is_active == True, FileAccess.access_type == "download")\
     .group_by(File.file_code)\
     .order_by(desc('downloads')).limit(10).all()

    return {
        "total_files": total_files,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "total_visits": total_visits,
        "total_downloads": total_downloads,
        "files_this_week": files_this_week,
        "visits_this_week": visits_this_week,
        "downloads_this_week": downloads_this_week,
        "top_files": [
            {
                "file_code": f.file_code,
                "filename": f.original_filename,
                "size_mb": round(f.file_size / 1024 / 1024, 2),
                "downloads": f.downloads
            } for f in top_files
        ]
    }

@app.get("/api/admin/files")
async def admin_all_files(
    admin_id: int = Query(...),
    q: Optional[str] = Query(None, description="поиск по имени/коду"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    _check_admin(admin_id)

    query = db.query(File).filter(File.is_active == True)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(File.original_filename.ilike(like), File.file_code.ilike(like)))

    total = query.count()
    files = query.order_by(desc(File.upload_date)).offset((page-1)*size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "files": [
            {
                "file_code": f.file_code,
                "filename": f.original_filename,
                "size_mb": round(f.file_size / 1024 / 1024, 2),
                "upload_date": f.upload_date.isoformat(),
                "user_id": f.user_id,
                "notify_visits": f.notify_visits,
                "notify_downloads": f.notify_downloads,
                "download_url": f"{BASE_URL}/{f.file_code}"
            } for f in files
        ]
    }

@app.get("/api/admin/logs/{file_code}")
async def admin_logs(
    file_code: str,
    admin_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db)
):
    _check_admin(admin_id)
    base = db.query(FileAccess).filter(FileAccess.file_code == file_code).order_by(desc(FileAccess.access_time))
    total = base.count()
    rows = base.offset((page-1)*size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "logs": [
            {
                "type": r.access_type,
                "ip": r.ip_address,
                "ua": r.user_agent,
                "country": r.country,
                "city": r.city,
                "time": r.access_time.isoformat()
            } for r in rows
        ]
    }

@app.get("/api/admin/logs/{file_code}/export.csv")
async def admin_logs_export_csv(file_code: str, admin_id: int = Query(...), db: Session = Depends(get_db)):
    _check_admin(admin_id)
    rows = db.query(FileAccess).filter(FileAccess.file_code == file_code).order_by(FileAccess.access_time.asc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["time", "type", "ip", "country", "city", "user_agent"])
    for r in rows:
        writer.writerow([r.access_time.isoformat(), r.access_type, r.ip_address, r.country or "", r.city or "", r.user_agent or ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.read()]), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="logs_{file_code}.csv"'
    })

@app.patch("/api/admin/files/{file_code}/toggle")
async def admin_toggle(
    file_code: str,
    admin_id: int = Form(...),
    field: str = Form(...),
    db: Session = Depends(get_db)
):
    _check_admin(admin_id)
    file = db.query(File).filter(File.file_code == file_code, File.is_active == True).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if field not in ("notify_visits", "notify_downloads"):
        raise HTTPException(status_code=400, detail="Bad field")
    setattr(file, field, not getattr(file, field))
    db.commit()
    return {"success": True, field: getattr(file, field)}

@app.delete("/api/admin/files/{file_code}")
async def admin_delete_file(file_code: str, admin_id: int = Form(...), db: Session = Depends(get_db)):
    _check_admin(admin_id)
    file = db.query(File).filter(File.file_code == file_code).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    path = f"api/files/{file.stored_filename}"
    if os.path.exists(path):
        os.remove(path)
    file.is_active = False
    db.commit()
    return {"success": True, "message": "File deleted by admin"}

@app.post("/api/admin/broadcast")
async def admin_broadcast(message: str = Form(...), admin_id: int = Form(...), db: Session = Depends(get_db)):
    _check_admin(admin_id)
    user_ids = db.query(File.user_id).filter(File.user_id.isnot(None)).distinct().all()
    user_ids = [uid[0] for uid in user_ids]
    success = 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="HTML")
            success += 1
        except Exception:
            pass
    return {"success": True, "message": f"Сообщение отправлено {success} из {len(user_ids)} пользователей"}


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "404.html",
        {
            "request": request,
            "title": "Droply - page not found"
        },
        status_code=404
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
