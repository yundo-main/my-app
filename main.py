import os

import pymysql
from fastapi import FastAPI, Form, HTTPException

app = FastAPI(title="my-app")


def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "mariadb"),
        user=os.getenv("DB_USER", "fcgiuser"),
        password=os.getenv("DB_PASSWORD", "fcgipass"),
        database=os.getenv("DB_NAME", "fcgidb"),
    )


@app.get("/")
def read_root():
    return {"message": "my-app my-app happy"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/register")
def register(username: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, password),
            )
        conn.commit()
    finally:
        conn.close()
    return {"message": "가입 완료!"}


@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username=%s AND password=%s",
                (username, password),
            )
            result = cursor.fetchone()
    finally:
        conn.close()
    if result:
        return {"message": "로그인 성공"}
    raise HTTPException(status_code=401, detail="로그인 실패")
