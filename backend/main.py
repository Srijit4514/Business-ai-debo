from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from typing import Optional
import uvicorn
import os
import shutil
import json
import uuid
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

client = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI(title="Business Analytics AI API")

# Setup upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Request Models
class ChatRequest(BaseModel):
    prompt: str
    filename: Optional[str] = None

class QueryRequest(BaseModel):
    query: str

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Business Analytics AI API"}

@app.post("/api/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Upload CSV or Excel")

    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {
            "filename": unique_filename,
            "original_name": file.filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat-analytics")
async def chat_analytics(request: ChatRequest):

    df_summary = "No dataset uploaded."

    if request.filename:

        file_path = os.path.join(UPLOAD_DIR, request.filename)

        if os.path.exists(file_path):

            try:
                if file_path.endswith(".csv"):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)

                df_summary = f"""
Columns: {", ".join(df.columns)}

Numerical Columns:
{", ".join(df.select_dtypes(include=[np.number]).columns)}

Sample Data:
{df.head(3).to_json(orient="records")}
"""

            except Exception as e:
                df_summary = f"Dataset error: {str(e)}"

    system_prompt = f"""
You are an expert Business Intelligence Analyst.

DATASET SUMMARY:
{df_summary}

USER PROMPT:
{request.prompt}

INSTRUCTIONS:

1. Analyze dataset and question.
2. Select BEST chart type:
BarChart, LineChart, PieChart, None

3. Chart rules:
LineChart → time series
BarChart → compare categories
PieChart → proportions

4. Return ONLY JSON.

FORMAT:

{{
"insight":"text explanation",
"chartType":"BarChart",
"chartData":[{{"name":"A","value":10}}],
"xAxisKey":"name",
"dataKeys":["value"]
}}
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=system_prompt,
            config={
                "response_mime_type": "application/json"
            }
        )

        result = json.loads(response.text)

        return result

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"LLM Processing Error: {str(e)}"
        )


@app.get("/api/analytics")
def get_analytics():

    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    revenue = [12000,15000,11000,18000,22000,25000,23000,28000,30000,32000,35000,40000]
    expenses = [8000,9000,8500,10000,12000,13000,12500,14000,15000,16000,17000,18000]

    profit = [r-e for r,e in zip(revenue,expenses)]

    return {

        "monthly_performance":[
            {"month":m,"revenue":r,"expenses":e,"profit":p}
            for m,r,e,p in zip(months,revenue,expenses,profit)
        ],

        "summary":{
            "total_revenue":sum(revenue),
            "total_profit":sum(profit),
            "avg_monthly_revenue":float(np.mean(revenue)),
            "growth_rate":"15%"
        },

        "category_distribution":[
            {"category":"Electronics","value":45},
            {"category":"Clothing","value":25},
            {"category":"Home & Garden","value":20},
            {"category":"Others","value":10}
        ]
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)