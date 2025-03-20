from app import asgi_app

if __name__ == '__main__':
    # This is only for local development
    import uvicorn
    uvicorn.run(asgi_app, host='0.0.0.0', port=8888, log_level="info")