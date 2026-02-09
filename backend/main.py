"""
Entrypoint to run the backend server.

From project root: cd backend && uvicorn app.main:app --reload
Or: cd backend && python main.py
"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
