from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
import os
from pathlib import Path
from dotenv import load_dotenv

# 🔍 DEBUG: Find and load .env file
current_dir = Path(__file__).resolve().parent  # app/
backend_dir = current_dir.parent                # backend/
env_path = backend_dir / ".env"

print("=" * 70)
print("🔍 DATABASE CONNECTION DEBUG")
print("=" * 70)
print(f"📂 Looking for .env at: {env_path}")
print(f"📂 .env file exists: {env_path.exists()}")

# Load .env file
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print("✅ .env loaded successfully")
else:
    print("❌ .env NOT FOUND! Trying current directory...")
    load_dotenv()

# Get environment variables
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "jobportal"  # ✅ Fixed: was "job_portal", should be "jobportal"

print(f"🔗 MONGO_URI: {MONGO_URI}")
print(f"📊 DATABASE_NAME: {DATABASE_NAME}")

if not MONGO_URI:
    print("❌ ERROR: MONGO_URI is None!")
    print("⚠️  Check your .env file has: MONGO_URI=mongodb+srv://...")
elif "localhost" in str(MONGO_URI) or "127.0.0.1" in str(MONGO_URI):
    print("⚠️  WARNING: Will connect to LOCAL MongoDB, not Atlas!")
elif "mongodb+srv" in str(MONGO_URI):
    print("✅ Will connect to MongoDB Atlas")

print("=" * 70)

client = None
db = None
fs_bucket = None


async def connect_to_mongo():
    global client, db, fs_bucket
    
    if not MONGO_URI:
        raise ValueError("MONGO_URI environment variable is not set! Check your .env file.")
    
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DATABASE_NAME]
    fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="resumes")
    await client.admin.command('ping')
    
    if "mongodb+srv" in MONGO_URI:
        print("✅ Connected to MongoDB Atlas!")
    else:
        print("⚠️  Connected to LOCAL MongoDB")


async def close_mongo_connection():
    if client:
        client.close()


def get_fs_bucket():
    return fs_bucket


def get_db():
    return db
