import re
from pathlib import PurePosixPath
class DSAClassifierService:
    """
    Classifies a LeetCode problem using the folder structure
    that already exists in the user's DSA repository.
    Important rule:
    Topic has pattern folders?
        YES -> classify the pattern
        NO  -> skip pattern classification
    """
    TOPIC_ALIASES = {
        "array": [
            "Arrays",
            "Array",
        ],
        "string": [
            "Strings",
            "String",
        ],
        "hash table": [
            "Hashing",
            "Hash Table",
        ],
        "hash map": [
            "Hashing",
            "Hash Map",
        ],
         "math": [
                    "Math & Geometry",
                ],
        "geometry": [
                    "Math & Geometry",
                ],
        "binary search": [
            "Binary Search",
        ],
        "linked list": [
            "Linked List",
        ],
        "stack": [
            "Stack",
        ],
        "queue": [
            "Queue",
        ],
        "tree": [
            "Trees",
            "Tree",
        ],
        "binary tree": [
            "Trees",
            "Binary Tree",
        ],
        "graph": [
            "Graphs",
            "Graph",
        ],
        "heap": [
            "Heap",
        ],
        "priority queue": [
            "Priority Queue",
            "Heap",
        ],
        "dynamic programming": [
            "Dynamic Programming",
        ],
        "greedy": [
            "Greedy",
        ],
        "recursion": [
            "Recursion",
        ],
        "backtracking": [
            "Backtracking",
        ],
        "two pointers": [
            "Two Pointers",
            "Slow-Fast Pointer",
            "Slow Fast Pointers",
            "Fast and Slow Pointers",
        ],
        "sliding window": [
            "Sliding Window",
        ],
        "prefix sum": [
            "Prefix Sum",
        ],
        "kadane's algorithm": [
            "Kadane",
            "Kadane's",
        ],
    }
    @staticmethod
    def normalize(value: str) -> str:
        """
        Normalize names for matching.
        Example:
            "Binary Search" -> "binarysearch"
            "Two Pointers"  -> "twopointers"
            "Kadane's"      -> "kadanes"
        """
        return re.sub(
            r"[^a-z0-9]",
            "",
            value.lower(),
        )
    @classmethod
    def get_top_level_topics(
        cls,
        tree: list,
    ) -> list[str]:
        """
        Get only the first-level DSA folders.
        Example:
            Arrays
            Binary Search
            Strings
            Hashing
        The values come directly from the repository.
        """
        topics = set()
        for item in tree:
            if item.get("type") != "tree":
                continue
            path = item.get("path", "")
            if not path:
                continue
            parts = PurePosixPath(
                path
            ).parts
            if parts:
                topics.add(
                    parts[0]
                )
        return sorted(topics)
    @classmethod
    def get_patterns_for_topic(
        cls,
        tree: list,
        topic: str,
    ) -> list[str]:
        """
        Detect actual pattern folders from the repository structure.
        A direct child of a topic is a PATTERN only when it contains
        at least one nested folder (a problem folder).
        A direct child containing only files is a PROBLEM folder.
        """
        prefix = topic.rstrip("/") + "/"
        direct_children = set()
        # Find direct children under the topic.
        for item in tree:
            if item.get("type") != "tree":
                continue
            item_path = item.get("path", "")
            if not item_path.startswith(prefix):
                continue
            relative = item_path[len(prefix):]
            if relative and "/" not in relative:
                direct_children.add(relative)
        patterns = []
        # A direct child is a pattern only if another TREE exists
        # below that child. Problem files are blobs, so a problem
        # folder containing only files is not mistaken for a pattern.
        for child in sorted(direct_children):
            child_prefix = prefix + child + "/"
            for item in tree:
                if item.get("type") != "tree":
                    continue
                item_path = item.get("path", "")
                if item_path.startswith(child_prefix):
                    patterns.append(child)
                    break
            else:
                # empty_pattern_folder: a brand-new pattern folder holds only
                # a README.md and no problems yet. A problem folder always
                # contains a Java or Python solution file, so a folder with
                # a README but no code files is a pattern folder.
                file_names = [
                    item.get("path", "")[len(child_prefix):].lower()
                    for item in tree
                    if item.get("type") == "blob"
                    and item.get("path", "").startswith(child_prefix)
                ]
                has_readme = any(
                    name == "readme.md" for name in file_names
                )
                has_code = any(
                    name.endswith((".java", ".py"))
                    for name in file_names
                )
                if has_readme and not has_code:
                    patterns.append(child)
        return sorted(set(patterns))
    @classmethod
    def match_topic(
        cls,
        topic_tags: list[str],
        available_topics: list[str],
    ) -> dict:
        """
        Match LeetCode topic tags to an existing
        DSA topic.
        Returns the actual folder name from the
        user's repository.
        """
        normalized_topics = {
            cls.normalize(topic): topic
            for topic in available_topics
        }
        candidates = []
        for tag in topic_tags:
            tag_lower = tag.lower().strip()
            # -------------------------------------------------
            # Direct match
            # -------------------------------------------------
            tag_normalized = cls.normalize(
                tag
            )
            if tag_normalized in normalized_topics:
                candidates.append(
                    {
                        "leetcode_tag": tag,
                        "dsa_topic": normalized_topics[
                            tag_normalized
                        ],
                        "match_type": "direct",
                    }
                )
                continue
            # -------------------------------------------------
            # Alias match
            # -------------------------------------------------
            aliases = cls.TOPIC_ALIASES.get(
                tag_lower,
                [],
            )
            for alias in aliases:
                alias_normalized = cls.normalize(
                    alias
                )
                if alias_normalized in normalized_topics:
                    candidates.append(
                        {
                            "leetcode_tag": tag,
                            "dsa_topic": normalized_topics[
                                alias_normalized
                            ],
                            "match_type": "alias",
                        }
                    )
                    break
        # -----------------------------------------------------
        # Topic priority
        #
        # A more specific topic should beat generic Array.
        #
        # Example:
        #
        # Array + Binary Search
        #             ↓
        #      Binary Search
        # -----------------------------------------------------
        topic_priority = [
            "Binary Search",
            "Linked List",
            "Stack",
            "Queue",
            "Graph",
            "Trees",
            "Tree",
            "Heap",
            "Priority Queue",
            "Dynamic Programming",
            "Greedy",
            "Backtracking",
            "Recursion",
            "Hashing",
            "Strings",
            "String",
            "Arrays",
            "Array",
        ]
        for preferred_topic in topic_priority:
            preferred_normalized = cls.normalize(
                preferred_topic
            )
            for candidate in candidates:
                candidate_normalized = cls.normalize(
                    candidate["dsa_topic"]
                )
                if (
                    candidate_normalized
                    == preferred_normalized
                ):
                    return {
                        "selected_topic": candidate[
                            "dsa_topic"
                        ],
                        "candidates": candidates,
                    }
        if candidates:
            return {
                "selected_topic": candidates[0][
                    "dsa_topic"
                ],
                "candidates": candidates,
            }
        return {
            "selected_topic": None,
            "candidates": [],
        }
    @classmethod
    def match_pattern(
        cls,
        topic_tags: list[str],
        title: str,
        available_patterns: list[str],
    ) -> dict:
        """
        Classify a pattern ONLY when the selected topic
        actually contains pattern folders.
        First try direct matching from LeetCode tags.
        Then try title matching.
        If no reliable match exists, return None.
        The project can later use AI for that case.
        """
        # -----------------------------------------------------
        # Case 1:
        # No patterns under this topic.
        # -----------------------------------------------------
        if not available_patterns:
            return {
                "selected_pattern": None,
                "classification_required": False,
                "reason": "Topic has no pattern folders",
                "candidates": [],
            }
        normalized_patterns = {
            cls.normalize(pattern): pattern
            for pattern in available_patterns
        }
        candidates = []
        # -----------------------------------------------------
        # Case 2:
        # Check explicit LeetCode topic tags.
        # -----------------------------------------------------
        for tag in topic_tags:
            tag_normalized = cls.normalize(
                tag
            )
            if tag_normalized in normalized_patterns:
                candidates.append(
                    {
                        "leetcode_tag": tag,
                        "dsa_pattern": normalized_patterns[
                            tag_normalized
                        ],
                        "match_type": "direct",
                    }
                )
                continue
            aliases = cls.TOPIC_ALIASES.get(
                tag.lower().strip(),
                [],
            )
            for alias in aliases:
                alias_normalized = cls.normalize(
                    alias
                )
                if (
                    alias_normalized
                    in normalized_patterns
                ):
                    candidates.append(
                        {
                            "leetcode_tag": tag,
                            "dsa_pattern": normalized_patterns[
                                alias_normalized
                            ],
                            "match_type": "alias",
                        }
                    )
                    break
        # -----------------------------------------------------
        # Case 3:
        # If exactly one reliable candidate exists,
        # use it.
        # -----------------------------------------------------
        if candidates:
            unique_patterns = []
            for candidate in candidates:
                pattern = candidate[
                    "dsa_pattern"
                ]
                if pattern not in unique_patterns:
                    unique_patterns.append(
                        pattern
                    )
            if len(unique_patterns) == 1:
                return {
                    "selected_pattern": unique_patterns[
                        0
                    ],
                    "classification_required": True,
                    "reason": (
                        "Pattern matched from "
                        "LeetCode topic tags"
                    ),
                    "candidates": candidates,
                }
        # -----------------------------------------------------
        # Case 4:
        # Try the problem title.
        #
        # Example:
        # "Longest Substring Without Repeating Characters"
        # may match Sliding Window.
        # -----------------------------------------------------
        title_normalized = cls.normalize(
            title
        )
        title_candidates = []
        for pattern in available_patterns:
            pattern_normalized = cls.normalize(
                pattern
            )
            # Simple normalized containment check.
            if pattern_normalized in title_normalized:
                title_candidates.append(
                    pattern
                )
        if len(title_candidates) == 1:
            return {
                "selected_pattern": title_candidates[
                    0
                ],
                "classification_required": True,
                "reason": (
                    "Pattern matched from "
                    "problem title"
                ),
                "candidates": [
                    {
                        "dsa_pattern": title_candidates[
                            0
                        ],
                        "match_type": "title",
                    }
                ],
            }
        # -----------------------------------------------------
        # Case 5:
        # Patterns exist, but we cannot safely classify.
        #
        # Do NOT randomly choose one.
        # AI can handle this later.
        # -----------------------------------------------------
        return {
            "selected_pattern": None,
            "classification_required": True,
            "reason": (
                "Patterns exist but no reliable "
                "pattern match was found"
            ),
            "candidates": [],
        }
    @classmethod
    def classify(
        cls,
        tree: list,
        topic_tags: list[str],
        title: str,
    ) -> dict:
        """
        Complete topic + pattern classification.
        Pattern-aware topic selection is performed BEFORE the generic
        topic-priority fallback. This prevents Binary Search from
        stealing problems that clearly match an Arrays pattern such as
        Two Pointers or Sliding Window.
        """
        topics = cls.get_top_level_topics(tree)
        topic_result = cls.match_topic(
            topic_tags=topic_tags,
            available_topics=topics,
        )
        candidates = topic_result["candidates"]
        if not candidates:
            return {
                "selected_topic": None,
                "topic_candidates": [],
                "patterns_exist": False,
                "available_patterns": [],
                "selected_pattern": None,
                "classification_status": "topic_not_found",
            }
        # -----------------------------------------------------
        # FIRST: look for a real pattern match across ALL
        # candidate topics.
        #
        # Examples:
        # 11 -> Arrays / Two Pointers
        # 15 -> Arrays / Two Pointers
        # 167 -> Arrays / Two Pointers
        # 209 -> Arrays / Sliding Window
        # -----------------------------------------------------
                # -----------------------------------------------------
        # EXPLICIT OVERRIDES: selected Array problems
        # Run BEFORE generic pattern matching.
        # -----------------------------------------------------
        array_pattern_overrides = {
            "best time to buy and sell stock": "Basic Traversal",
            "max consecutive ones": "Basic Traversal",
        }

        override_pattern = array_pattern_overrides.get(
            title.strip().lower()
        )

        if override_pattern:
            for candidate in candidates:
                candidate_topic = candidate["dsa_topic"]

                if cls.normalize(candidate_topic) != cls.normalize("Arrays"):
                    continue

                available_patterns = cls.get_patterns_for_topic(
                    tree=tree,
                    topic=candidate_topic,
                )

                actual_pattern = next(
                    (
                        pattern
                        for pattern in available_patterns
                        if cls.normalize(pattern)
                        == cls.normalize(override_pattern)
                    ),
                    None,
                )

                if actual_pattern:
                    return {
                        "selected_topic": candidate_topic,
                        "topic_candidates": candidates,
                        "patterns_exist": True,
                        "available_patterns": available_patterns,
                        "selected_pattern": actual_pattern,
                        "pattern_reason": (
                            "Explicit classification rule for this problem"
                        ),
                        "classification_status": "topic_and_pattern",
                    }

        # -----------------------------------------------------
        # GENERIC PATTERN MATCHING
        # -----------------------------------------------------
        
        
        pattern_matches = []
        for candidate in candidates:
            candidate_topic = candidate["dsa_topic"]
            available_patterns = cls.get_patterns_for_topic(
                tree=tree,
                topic=candidate_topic,
            )
            if not available_patterns:
                continue
            normalized_patterns = {
                cls.normalize(pattern): pattern
                for pattern in available_patterns
            }
            for tag_index, tag in enumerate(topic_tags):
                tag_normalized = cls.normalize(tag)
                if tag_normalized in normalized_patterns:
                    pattern_matches.append(
                        {
                            "tag_index": tag_index,
                            "topic": candidate_topic,
                            "available_patterns": available_patterns,
                            "pattern": normalized_patterns[tag_normalized],
                            "match_type": "direct",
                        }
                    )
                    continue
                aliases = cls.TOPIC_ALIASES.get(
                    tag.lower().strip(),
                    [],
                )
                for alias in aliases:
                    alias_normalized = cls.normalize(alias)
                    if alias_normalized in normalized_patterns:
                        pattern_matches.append(
                            {
                                "tag_index": tag_index,
                                "topic": candidate_topic,
                                "available_patterns": available_patterns,
                                "pattern": normalized_patterns[
                                    alias_normalized
                                ],
                                "match_type": "alias",
                            }
                        )
                        break
        if pattern_matches:
            # LeetCode's tag order is our deterministic tie-breaker.
            selected = min(
                pattern_matches,
                key=lambda item: item["tag_index"],
            )
            return {
                "selected_topic": selected["topic"],
                "topic_candidates": candidates,
                "patterns_exist": True,
                "available_patterns": selected[
                    "available_patterns"
                ],
                "selected_pattern": selected["pattern"],
                "pattern_reason": (
                    "Pattern matched from LeetCode topic tags"
                ),
                "classification_status": "topic_and_pattern",
            }
        # -----------------------------------------------------
        # SECOND: no pattern match.
        # Use existing topic priority.
        # -----------------------------------------------------
        topic_priority = [
            "Binary Search",
            "Linked List",
            "Stack",
            "Queue",
            "Graph",
            "Graphs",
            "Trees",
            "Tree",
            "Heap",
            "Priority Queue",
            "Dynamic Programming",
            "Greedy",
            "Backtracking",
            "Recursion",
            "Hashing",
            "Strings",
            "String",
            "Arrays",
            "Array",
        ]
        normalized_candidates = {
            cls.normalize(candidate["dsa_topic"]): candidate["dsa_topic"]
            for candidate in candidates
        }
        selected_topic = None
        for preferred_topic in topic_priority:
            normalized_preferred = cls.normalize(preferred_topic)
            if normalized_preferred in normalized_candidates:
                selected_topic = normalized_candidates[
                    normalized_preferred
                ]
                break
        if selected_topic is None:
            selected_topic = candidates[0]["dsa_topic"]
        available_patterns = cls.get_patterns_for_topic(
            tree=tree,
            topic=selected_topic,
        )

        if available_patterns:
            return {
                "selected_topic": selected_topic,
                "topic_candidates": candidates,
                "patterns_exist": True,
                "available_patterns": available_patterns,
                "selected_pattern": None,
                "pattern_reason": (
                    "Patterns exist but no reliable pattern match was found"
                ),
                "classification_status": "pattern_needs_ai",
            }
        return {
            "selected_topic": selected_topic,
            "topic_candidates": candidates,
            "patterns_exist": False,
            "available_patterns": [],
            "selected_pattern": None,
            "pattern_reason": "Topic has no pattern folders",
            "classification_status": "topic_only",
        }
    @staticmethod
    def build_destination(
        topic: str,
        pattern: str | None,
        problem_folder_name: str,
    ) -> str:
        """
        Build the DSA destination.
        With pattern:
            Arrays/Two Pointers/283_Move Zeroes
        Without pattern:
            Binary Search/33_Search in Rotated Sorted Array
        """
        if pattern:
            return (
                f"{topic}/"
                f"{pattern}/"
                f"{problem_folder_name}"
            )
        return (
            f"{topic}/"
            f"{problem_folder_name}"
        )
