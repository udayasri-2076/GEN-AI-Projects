from app.schemas.problem import ProblemCreate, ProblemUpdate


# Temporary data for learning
problems = [
    {
        "id": 1,
        "title": "Two Sum",
        "difficulty": "Easy"
    },
    {
        "id": 2,
        "title": "Binary Tree",
        "difficulty": "Medium"
    }
]


def get_all_problems():
    return problems


def get_problem_by_id(problem_id: int):
    for problem in problems:
        if problem["id"] == problem_id:
            return problem

    return None


def create_problem(problem: ProblemCreate):
    new_problem = {
        "id": len(problems) + 1,
        "title": problem.title,
        "difficulty": problem.difficulty
    }

    problems.append(new_problem)

    return new_problem


def update_problem(problem_id: int, problem: ProblemUpdate):
    existing_problem = get_problem_by_id(problem_id)

    if existing_problem is None:
        return None

    if problem.title is not None:
        existing_problem["title"] = problem.title

    if problem.difficulty is not None:
        existing_problem["difficulty"] = problem.difficulty

    return existing_problem


def delete_problem(problem_id: int):
    existing_problem = get_problem_by_id(problem_id)

    if existing_problem is None:
        return None

    problems.remove(existing_problem)

    return existing_problem