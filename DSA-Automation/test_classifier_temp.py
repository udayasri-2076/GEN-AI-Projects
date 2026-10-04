from app.services.dsa_classifier_service import DSAClassifierService

tree = [
    {"path": "Arrays", "type": "tree"},
    {"path": "Arrays/Two Pointers", "type": "tree"},
    {"path": "Arrays/Two Pointers/11_Container With Most Water", "type": "tree"},
    {"path": "Arrays/Sliding Window", "type": "tree"},
    {"path": "Binary Search", "type": "tree"},
]

tests = [
    (["Math"], "Palindrome Number"),
    (["Array", "Dynamic Programming"], "Best Time to Buy and Sell Stock"),
    (["Array"], "Max Consecutive Ones"),
    (["Array", "Binary Search"], "Find Peak Element"),
]

for tags, title in tests:
    result = DSAClassifierService.classify(
        tree=tree,
        topic_tags=tags,
        title=title,
    )
    print(f"\n{title} | tags={tags}")
    print(result)
