from pydantic import BaseModel

class ProblemCreate(BaseModel):
    title:str
    difficulty:str

class ProblemUpdate(BaseModel):
    title:str|None=None
    difficulty:str| None=None

class ProblemResponse(BaseModel):

    id:int
    title:str
    difficulty:str