from bvbank import BVBank
import json
import requests
import json
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import sys
import traceback
from api_response import APIResponse


app = FastAPI()
@app.get("/")
def read_root():
    return {"Hello": "World"}


class LoginDetails(BaseModel):
    username: str
    password: str
    account_number: str
    proxy_list: list
@app.post('/login', tags=["login"])
async def login_api(input: LoginDetails):
    try:
        bvbank = BVBank(input.username, input.password, input.account_number,input.proxy_list)
        session_raw = await bvbank.login()
        return APIResponse.json_format(session_raw)
    except Exception as e:
        response = str(e)
        print(traceback.format_exc())
        print(sys.exc_info()[2])
        return APIResponse.json_format(response)
    

@app.post('/get_balance', tags=["get_balance"])
async def get_balance_api(input: LoginDetails):
    try:
        bvbank = BVBank(input.username, input.password, input.account_number,input.proxy_list)
        balance = await bvbank.get_balance(input.account_number)
        return APIResponse.json_format(balance)
    except Exception as e:
        response = str(e)
        print(traceback.format_exc())
        print(sys.exc_info()[2])
        return APIResponse.json_format(response)
    
class Transactions(BaseModel):
    username: str
    password: str
    account_number: str
    from_date: str
    to_date: str
    latest: bool
    proxy_list: list
    
@app.post('/get_transactions', tags=["get_transactions"])
async def get_transactions_api(input: Transactions):
    try:
        bvbank = BVBank(input.username, input.password, input.account_number,input.proxy_list)
        history = await bvbank.get_transactions(input.account_number,input.from_date,input.to_date,input.latest)
        return APIResponse.json_format(history)
    except Exception as e:
        response = str(e)
        print(traceback.format_exc())
        print(sys.exc_info()[2])
        return APIResponse.json_format(response)


if __name__ == "__main__":
    uvicorn.run(app ,host='0.0.0.0', port=3000)
    
    