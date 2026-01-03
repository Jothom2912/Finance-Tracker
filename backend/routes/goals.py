from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Body
from typing import List, Optional, Dict, Any

from backend.shared.schemas.goal import Goal as GoalSchema, GoalCreate, GoalBase
from backend.services import goal_service
from backend.auth import decode_token
from backend.repository import get_account_repository

router = APIRouter(
    prefix="/goals",
    tags=["Goals"],
)

def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
) -> Optional[int]:
    account_id = None
    if x_account_id:
        try:
            return int(x_account_id)
        except ValueError:
            pass
    
    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            account_repo = get_account_repository()
            accounts = account_repo.get_all(user_id=token_data.user_id)
            if accounts:
                return accounts[0]["idAccount"]
    return None

@router.post("/", response_model=GoalSchema, status_code=status.HTTP_201_CREATED)
def create_goal_route(
    goal_data: Dict[str, Any] = Body(...),
    account_id: Optional[int] = Depends(get_account_id_from_headers)
):
    if 'Account_idAccount' not in goal_data or goal_data.get('Account_idAccount') is None:
        if not account_id:
            raise HTTPException(status_code=400, detail="Account ID mangler.")
        goal_data['Account_idAccount'] = account_id
    
    try:
        goal = GoalCreate(**goal_data)
        return goal_service.create_goal(goal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[GoalSchema])
def read_goals_route(
    account_id: Optional[int] = Query(None),
    account_id_from_header: Optional[int] = Depends(get_account_id_from_headers)
):
    final_account_id = account_id or account_id_from_header
    if not final_account_id:
        raise HTTPException(status_code=400, detail="Account ID mangler.")
    return goal_service.get_goals_by_account(final_account_id)

@router.get("/{goal_id}", response_model=GoalSchema)
def read_goal_route(goal_id: int):
    goal = goal_service.get_goal_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Mål ikke fundet.")
    return goal

@router.put("/{goal_id}", response_model=GoalSchema)
def update_goal_route(goal_id: int, goal_data: GoalBase):
    updated = goal_service.update_goal(goal_id, goal_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Mål ikke fundet.")
    return updated

@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_route(goal_id: int):
    if not goal_service.delete_goal(goal_id):
        raise HTTPException(status_code=404, detail="Mål ikke fundet.")
    return None
