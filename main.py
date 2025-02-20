from fastapi import FastAPI
from pydantic_settings import BaseSettings
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

class Settings(BaseSettings):
    PORT: int
    DATABASE_URL: str

    class Config:
        env_file = '.env'

settings = Settings()

cred = credentials.Certificate('credentials.json')
print(settings.DATABASE_URL)
firebase_app = firebase_admin.initialize_app(cred, {
    'databaseURL': settings.DATABASE_URL
})
db = firestore.client(app=firebase_app, database_id="users")
users_ref = db.collection("users")
docs = users_ref.stream()

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def get_users():
    users = []
    for doc in docs:
        users.append(doc.to_dict())
    return users

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)