from fastapi import FastAPI,Request
from contextlib import asynccontextmanager
from fastapi.exception_handlers import (http_exception_handler,request_validation_exception_handler)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException,status,Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from schemas import PostCreate,PostResponse
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import models
from database import Base,engine,get_db
from schemas import PostCreate,PostResponse,UserCreate,UserResponse,PostUpdate,UserUpdate

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


#returning html pages
@app.get('/',include_in_schema=False,name="home")
@app.get('/posts',include_in_schema=False,name="posts")
async def home(request:Request,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)))
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
    result=db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id==user_id))
    posts=result.scalars().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts":posts,"user":user,"title":f"{user.username}'s Posts"}
    )



#returning json 
@app.post("/api/users",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
async def create_user(user:UserCreate,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.username==user.username))
    existing_user=result.scalars().first()
    if existing_user:
        raise HTTPException(detail="username already exist",status_code=status.HTTP_400_BAD_REQUEST)
    result=await db.execute(select(models.User).where(models.User.email==user.email))
    existing_email=result.scalars().first()
    if existing_email:
        raise HTTPException(detail="email already exist",status_code=status.HTTP_400_BAD_REQUEST)
    new_user=models.User(
        username=user.username,
        email=user.email
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@app.get('/api/users',response_model=list[UserResponse])
def get_users(db:Annotated[Session,Depends(get_db)]):
    result=db.execute(select(models.User))
    users=result.scalars().all()
    return users


@app.get("/api/users/{user_id}",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
async def get_user(user_id:int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="user not found")

@app.patch("/api/users/{user_id}",response_model=UserResponse)
async def user_update(
    user_id:int,
    user_updated:UserUpdate,
    db:Annotated[AsyncSession,Depends(get_db)]
):
    result= await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    if user_updated.username is not None and user_updated.username!=user.username:
        result=await db.execute(select(models.User).where(models.User.username==user_updated.username))
        existing_user=result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="username already exist"
            )
    if user_updated.email is not None and user_updated.email!=user.email:
        result=await db.execute(
            select(models.User).where(models.User.email==user_updated.email)
        )
        existing_email=result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    if user_updated.username is not None:
        user.username=user_updated.username
    if user_updated.email is not None:
        user.email=user_updated.email
    if user_updated.image_file is not None:
        user.image_file=user_updated.image_file
    await db.commit()
    await db.refresh(user)
    return user


@app.get("/api/users/{user_id}/posts",response_model=list[PostResponse])
async def get_user_posts(user_id:int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.user_id==user_id))
    posts=result.scalars().all()
    return posts


@app.delete("/api/users/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id:int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    await db.delete(user)
    await db.commit()


@app.get('/api/posts',response_model=list[PostResponse])
async def get_posts(db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)))
    posts=result.scalars().all()
    return posts
    
@app.put("/api/posts/{post_id}",response_model=PostResponse)
async def update_post_full(post_id:int,post_data:PostCreate,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).where(models.Post.id==post_id))
    post=result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,detail="post not found"
        )
    if post_data.user_id!=post.user_id:
        result=await db.execute(select(models.User).where(models.User.id==post_data.user_id))
        user=result.scalars().first()
        if not user:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    post.title=post_data.title
    post.content=post_data.content
    post.user_id=post_data.user_id
    await db.commit()
    await db.refresh(post,attribute_names=['author'])
    return post


@app.patch("/api/posts/{post_id}",response_model=PostResponse)
async def update_post_partial(post_id:int,post_data:PostUpdate,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).where(models.Post.id==post_id))
    post=result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,detail="post not found"
        )
    update_data=post_data.model_dump(exclude_unset=True)
    for item,value in update_data.items():
        setattr(post,item,value)
    await db.commit()
    await db.refresh(post,attribute_names=['author'])
    return post


@app.get("/api/posts/{post_id}",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
async def get_post(post_id: int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id==post_id))
    post=result.scalars().first()
    if post:
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Post not found")



@app.post("/api/posts",response_model=PostResponse,status_code=status.HTTP_201_CREATED)
async def create_post(post:PostCreate,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id==post.user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    new_post=models.Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post,attribute_names=['author'])
    return new_post
    
@app.delete("/api/posts/{post_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id:int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.Post).where(models.Post.id==post_id))
    post=result.scalars().first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="no such post")
    await db.delete(post)
    await db.commit()



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