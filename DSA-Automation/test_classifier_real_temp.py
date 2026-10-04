import asyncio
from dotenv import load_dotenv
from app.services.github_service import GitHubService
from app.services.dsa_classifier_service import DSAClassifierService

async def main():
    load_dotenv()
    github = GitHubService()
    repo = __import__("os").getenv("DSA_REPO")

    if not repo:
        print("ERROR: DSA_REPO is missing in .env")
        return

    data = await github.get_repository_tree(repo=repo, branch="main")
    tree = data.get("tree", [])

    print("\nTOP-LEVEL FOLDERS:")
    for topic in DSAClassifierService.get_top_level_topics(tree):
        print(" -", topic)

    print("\nCLASSIFICATION TESTS:")
    tests = [
        (["Math"], "Palindrome Number"),
        (["Array", "Dynamic Programming"], "Best Time to Buy and Sell Stock"),
        (["Array"], "Max Consecutive Ones"),
        (["Array", "Binary Search"], "Find Peak Element"),
    ]

    for tags, title in tests:
        result = DSAClassifierService.classify(
            tree=tree, topic_tags=tags, title=title
        )
        print(f"\n{title} | tags={tags}")
        print("Topic:", result.get("selected_topic"))
        print("Pattern:", result.get("selected_pattern"))
        print("Status:", result.get("classification_status"))
        print("Available patterns:", result.get("available_patterns"))

asyncio.run(main())
