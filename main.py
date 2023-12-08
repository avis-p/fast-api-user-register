from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from asyncpg import create_pool
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

# PostgreSQL Configuration
DATABASE_URL = "postgresql://user:password@localhost/db_name"



# Create a pool of PostgreSQL connections
async def get_pool():
    return await create_pool(DATABASE_URL)

# MongoDB Configuration
MONGO_URL = "mongodb://localhost:27017"
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["user_profile_db"]
profile_collection = db["profile"]



class UserBase(BaseModel):
    email: str
    password: str
    phone: str

class User(UserBase):
    user_id: int
    full_name: str
    profile_picture: str = ""

    class Config:
        orm_mode = True

class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str
    phone: str
    profile_picture: str



# PostgreSQL Table for Users
async def create_user_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                full_name VARCHAR(100),
                email VARCHAR(100) UNIQUE,
                password VARCHAR(100),
                phone VARCHAR(20) UNIQUE
            )
            """
        )


# MongoDB Collection for Profile Pictures
async def save_profile_picture(profile_picture):
    await profile_collection.insert_one(profile_picture)


# Register User Endpoint
@app.post("/register/", response_model=UserCreate)
async def register_user(user: UserCreate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        
        query = "INSERT INTO users (full_name, email, password, phone) VALUES ($1, $2, $3, $4) RETURNING *"
        try:
            result = await conn.fetchrow(query, user.full_name, user.email, user.password, user.phone)
            user_id = result[0]
            
            profile_data = {"user_id": user_id, "profile_picture": user.profile_picture}
            await profile_collection.insert_one(profile_data)
            return user
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))





# Get User Details Endpoint
@app.get("/user/{user_id}/", response_model=User)
async def get_user_details(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE user_id = $1"
        result = await conn.fetchrow(query, user_id)
        if result:
            user_data = User(
                user_id=user_id,
                full_name=result['full_name'],
                email=result['email'],
                password=result['password'],
                phone=result['phone'],
            )

            profile_result = await profile_collection.find_one({"user_id": user_id})
            if profile_result:
                user_data.profile_picture = profile_result.get("profile_picture", "")  # Adjust as needed
            else:
                user_data.profile_picture = ""  # Set a default value when profile_picture is missing
            return user_data
        else:
            raise HTTPException(status_code=404, detail="User not found")

@app.on_event("startup")
async def on_startup():
    await create_user_table()