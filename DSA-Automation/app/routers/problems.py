from fastapi import APIRouter, HTTPException
from app.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse
)
from app.services import problem_service

router = APIRouter()


@router.get("/problems", response_model=list[ProblemResponse])
def get_problems():
    return problem_service.get_all_problems()


@router.get("/problems/{problem_id}", response_model=ProblemResponse)
def get_problem(problem_id: int):
    problem = problem_service.get_problem_by_id(problem_id)

    if problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )

    return problem


@router.post(
    "/problems",
    response_model=ProblemResponse,
    status_code=201
)
def create_problem(problem: ProblemCreate):
    return problem_service.create_problem(problem)


@router.patch(
    "/problems/{problem_id}",
    response_model=ProblemResponse
)
def update_problem(
    problem_id: int,
    problem: ProblemUpdate
):
    updated_problem = problem_service.update_problem(
        problem_id,
        problem
    )

    if updated_problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )

    return updated_problem


@router.delete("/problems/{problem_id}")
def delete_problem(problem_id: int):
    deleted_problem = problem_service.delete_problem(problem_id)

    if deleted_problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found"
        )

    return {
        "message": "Problem deleted",
        "problem_id": problem_id
    }