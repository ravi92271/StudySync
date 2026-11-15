from fastapi import FastAPI

app = FastAPI(title = "StudySync")

@app.get("/")
def root():
    return {"message": "Hello World"}