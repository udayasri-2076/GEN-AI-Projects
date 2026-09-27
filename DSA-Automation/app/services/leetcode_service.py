import httpx


class LeetCodeService:
    """
    Handles public LeetCode problem metadata.
    """

    GRAPHQL_URL = "https://leetcode.com/graphql"

    QUERY = """
    query questionData($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            questionFrontendId
            title
            titleSlug
            topicTags {
                name
                slug
            }
        }
    }
    """

    async def get_problem_metadata(
        self,
        title_slug: str,
    ) -> dict:
        """
        Get official LeetCode metadata using the problem slug.
        """

        payload = {
            "query": self.QUERY,
            "variables": {
                "titleSlug": title_slug,
            },
            "operationName": "questionData",
        }

        headers = {
            "Content-Type": "application/json",
            "Referer": (
                f"https://leetcode.com/problems/"
                f"{title_slug}/"
            ),
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
        }

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.post(
                self.GRAPHQL_URL,
                json=payload,
                headers=headers,
            )

        response.raise_for_status()

        data = response.json()

        # -----------------------------------------------------
        # Handle GraphQL errors
        # -----------------------------------------------------

        if data.get("errors"):
            raise ValueError(
                f"LeetCode GraphQL error: "
                f"{data['errors']}"
            )

        question = (
            data.get("data", {})
            .get("question")
        )

        if not question:
            raise ValueError(
                f"LeetCode problem not found: "
                f"{title_slug}"
            )

        topic_tags = [
            tag.get("name")
            for tag in question.get(
                "topicTags",
                [],
            )
            if tag.get("name")
        ]

        return {
            "problem_number": int(
                question[
                    "questionFrontendId"
                ]
            ),
            "title": question[
                "title"
            ],
            "title_slug": question[
                "titleSlug"
            ],
            "topic_tags": topic_tags,
        }