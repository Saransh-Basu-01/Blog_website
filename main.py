from fastapi import FastAPI,Request
from contextlib import asynccontextmanager
from fastapi.exception_handlers import (http_exception_handler,request_validation_exception_handler)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException,status,Depends
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import models
from database import Base,engine,get_db
from routers import post,users

@asynccontextmanager
async def lifespan(_app:FastAPI):
    #startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    #shutdown
    await engine.dispose()

app=FastAPI(lifespan=lifespan)

app.mount("/static",StaticFiles(directory="static"),name="static")
app.mount("/media",StaticFiles(directory="media"),name="media")

templates=Jinja2Templates(directory="templates")

app.include_router(users.router,prefix="/api/users",tags=["users"])
app.include_router(post.router,prefix="/api/posts",tags=["posts"])

#returning html pages
@app.get('/',include_in_schema=False,name="home")
@app.get('/posts',include_in_schema=False,name="posts")
async def home(request:Request,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)).order_by(models.Post.date_posted.desc()))
    posts=result.scalars().all()
    return templates.TemplateResponse(request,"home.html",{"posts":posts,"title":"Home"})



@app.get("/posts/{post_id}",include_in_schema=False)
async def post_page(request:Request,post_id:int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id==post_id))
    post=result.scalars().first()
    if post:
        title=post.title[:50]
        return templates.TemplateResponse(
            request,
            "post.html",
            {"post":post,"title":title}
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="post not found")



@app.get("/users/{user_id}/posts",include_in_schema=False,name="user_posts")
async def user_posts_page(
    request:Request,
    user_id:int,
    db:Annotated[AsyncSession,Depends(get_db)]
):
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id==user_id).order_by(models.Post.date_posted.desc()))
    posts=result.scalars().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts":posts,"user":user,"title":f"{user.username}'s Posts"}
    )

@app.get("/Login",include_in_schema=False)
async def login_page(request:Request):
    return templates.TemplateResponse(
        request,
        "Login.html",
        {"title":"login"}
    )


@app.get("/Register",include_in_schema=False)
async def register_page(request:Request):
    return templates.TemplateResponse(
        request,
        "Register.html",
        {"title":"register"}
    )

@app.get("/Account",include_in_schema=False)
async def account_page(request:Request):
    return templates.TemplateResponse(
        request,
        "Account.html",
        {"title":"Account"}
    )

@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception)

    message = (
        exception.detail
        if exception.detail
        else "An error occurred. Please check your request and try again."
    )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message,
        },
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )