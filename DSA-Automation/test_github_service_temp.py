import asyncio
from dotenv import load_dotenv
from app.services.github_service import GitHubService

async def main():
    load_dotenv()
    github = GitHubService()
    print("GitHub service:", type(github).__name__)

asyncio.run(main())
