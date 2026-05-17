from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,status,UploadFile,Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import models
from database import get_db
from schemas import PostResponse,UserCreate,UserUpdate,UserPrivate,UserPublic,Token,PaginatedPostsResponse
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from auth import create_access_token,hash_password,verify_password,CurrentUser
from config import settings
from PIL import UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from image_utils import delete_profile_image,process_profile_image

router=APIRouter()
@router.post("",response_model=UserPrivate,status_code=status.HTTP_201_CREATED)
async def create_user(user:UserCreate,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(
        select(models.User).where(func.lower(models.User.username)==user.username.lower())
        )
    
    existing_user=result.scalars().first()
    if existing_user:
        raise HTTPException(detail="username already exist",status_code=status.HTTP_400_BAD_REQUEST)
    result=await db.execute(
        select(models.User).where(
            func.lower(models.User.email)==user.email.lower()))

    existing_email=result.scalars().first()

    if existing_email:
        raise HTTPException(detail="email already exist",status_code=status.HTTP_400_BAD_REQUEST)
    
    new_user=models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash=hash_password(user.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/token",response_model=Token)
async def login_for_access_token(
    form_data:Annotated[OAuth2PasswordRequestForm,Depends()],
    db:Annotated[AsyncSession,Depends(get_db)]
):
    result=await db.execute(
        select(models.User).where(
            func.lower(models.User.email)==form_data.username.lower()
        )
    )
    user=result.scalars().first()
    if not user or not verify_password(form_data.password,user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate":"Bearer"}
        )
    access_token_expires=timedelta(minutes=settings.access_token_expire_minutes)
    access_token=create_access_token(
        data={"sub":str(user.id)},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token,token_type="bearer")


@router.get("/me",response_model=UserPrivate)
async def get_current_user(
   current_user:CurrentUser
):
    return current_user


@router.get('',response_model=list[UserPublic])
async def get_users(db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User))
    users=result.scalars().all()
    return users


@router.get("/{user_id}",response_model=UserPublic,status_code=status.HTTP_201_CREATED)
async def get_user(user_id:int,db:Annotated[AsyncSession,Depends(get_db)]):
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="user not found")

@router.patch("/{user_id}",response_model=UserPrivate)
async def user_update(
    user_id:int,
    user_updated:UserUpdate,
    current_user:CurrentUser,
    db:Annotated[AsyncSession,Depends(get_db)]
):
    if user_id !=current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to update this user"
        )
    # result= await db.execute(select(models.User).where(models.User.id==user_id))
    # user=result.scalars().first()
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="user not found"
    #     )
    if (
        user_updated.username is not None and user_updated.username.lower()!=current_user.username.lower()
        ):
        result=await db.execute(select(models.User).where(func.lower(models.User.username)==user_updated.username.lower()))
        existing_user=result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="username already exist"
            )
    if user_updated.email is not None and user_updated.email.lower()!=current_user.email.lower():
        result=await db.execute(
            select(models.User).where(func.lower(models.User.email)==user_updated.email.lower())
        )
        existing_email=result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    if user_updated.username is not None:
        current_user.username=user_updated.username
    if user_updated.email is not None:
        current_user.email=user_updated.email.lower()
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/{user_id}/posts",response_model=PaginatedPostsResponse)
async def get_user_posts(
    user_id:int,
    db:Annotated[AsyncSession,Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.posts_per_page,
    ):
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    count_result = await db.execute(
        select(func.count())
        .select_from(models.Post)
        .where(models.Post.user_id == user_id),
    )
    total = count_result.scalar() or 0
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit),
    )
    posts=result.scalars().all()
    has_more = skip + len(posts) < total
    return PaginatedPostsResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.delete("/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id:int,
                      current_user:CurrentUser,
                      db:Annotated[AsyncSession,Depends(get_db)]):
    if user_id !=current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to delete this user"
        )
    result=await db.execute(select(models.User).where(models.User.id==user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    old_filename=user.image_file
    await db.delete(user)
    await db.commit()
    if old_filename:
        delete_profile_image(old_filename)


@router.patch("/{user_id}/picture",response_model=UserPrivate)
async def upload_profile_picture(
    user_id:int,
    file:UploadFile,
    current_user:CurrentUser,
    db:Annotated[AsyncSession,Depends(get_db)]
):
    if current_user.id!=user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's picture"
        )
    content=await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large.Maximum size is {settings.max_upload_size_bytes//(1024*1024)}MB"
        )
    try:
        new_filename=await run_in_threadpool(process_profile_image,content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file.please upload a valid image"
        ) from err
    
    old_filename=current_user.image_file
    current_user.image_file=new_filename
    await db.commit()
    await db.refresh(current_user)
    if old_filename:
        delete_profile_image(old_filename)
    return current_user


@router.delete("/{user_id}/picture",response_model=UserPrivate)
async def delete_user_picture(
    user_id:int,
    current_user:CurrentUser,
    db:Annotated[AsyncSession,Depends(get_db)]
):
    if current_user!=user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorized to delete this users picture"
        )
    old_filename=current_user.image_file
    if old_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no profile picture to delete"
        )
    current_user.image_file=None
    await db.commit()
    await db.refresh(current_user)
    delete_profile_image(old_filename)
    return current_user
    