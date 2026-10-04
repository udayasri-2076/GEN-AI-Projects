from pathlib import PurePosixPath


class DSAStructureService:
    """
    Converts the raw GitHub DSA repository tree
    into the user's topic/pattern structure.
    """

    @staticmethod
    def build_taxonomy(
        tree: list,
    ) -> dict:
        """
        Build:

        {
            "topics": [...],
            "patterns": {
                "Arrays": [...],
                "Binary Search": [...],
                ...
            }
        }

        We do not invent folders.

        Everything comes directly from the
        folders that already exist in the DSA repo.
        """

        folder_paths = sorted(
            {
                item.get("path", "")
                for item in tree
                if item.get("type") == "tree"
                and item.get("path")
            }
        )

        topics = set()

        patterns = {}

        for folder_path in folder_paths:

            parts = PurePosixPath(
                folder_path
            ).parts

            if not parts:
                continue

            # -------------------------------------------------
            # First level = Topic
            # Example:
            # Arrays
            # Strings
            # Binary Search
            # -------------------------------------------------

            topic = parts[0]

            topics.add(topic)

            if topic not in patterns:
                patterns[topic] = set()

            # -------------------------------------------------
            # Second level = Pattern
            # Example:
            #
            # Arrays/Two Pointers
            # Arrays/Sliding Window
            # -------------------------------------------------

            if len(parts) >= 2:

                pattern = parts[1]

                patterns[topic].add(
                    pattern
                )

        # Convert sets to sorted lists
        sorted_topics = sorted(
            topics
        )

        sorted_patterns = {
            topic: sorted(
                pattern_list
            )
            for topic, pattern_list
            in patterns.items()
        }

        return {
            "topics": sorted_topics,
            "patterns": sorted_patterns,
        }