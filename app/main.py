from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


app = FastAPI()

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,          # <-- Pasa request como argumento de palabra clave
        name="index.html",        # <-- El nombre de la plantilla
        context={}                # <-- Tus variables van aquí (puedes dejarlo vacío si no usas ninguna)
    )
