from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
def hello():
    return {"message" : "hello world"}

from pydantic import BaseModel

class Item(BaseModel):
    name : str
    quantity : int
    goated : bool

@app.post("/items")
def create_item(item : Item):
    return {"received" : item}
    
    