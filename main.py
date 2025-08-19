import json
import os
import gspread
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- 1. CONFIGURACIÓN INICIAL ---
load_dotenv()

# Cargar las credenciales de forma segura
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SHEET_NAME = os.getenv("SHEET_NAME")

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # Usamos un modelo rápido y eficiente


def load_inventory():
    """Carga los datos de Google Sheets a un DataFrame de Pandas."""
    try:
        # Autenticar con Google Sheets
        google_creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if not google_creds_json:
            gc = gspread.service_account(filename="credentials.json")
        else:
            # Para que funcione en Railway
            creds_dict = json.loads(google_creds_json)
            gc = gspread.service_account_from_dict(creds_dict)
        # Abrir la hoja de cálculo
        worksheet = gc.open(SHEET_NAME).sheet1
        # Obtener todos los datos y crear el DataFrame
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        print("Inventario cargado exitosamente.")
        return df
    except Exception as e:
        print(f"Error al cargar la hoja de Google Sheets: {e}")
        return None


# Cargar el inventario UNA VEZ al iniciar el bot
inventory_df = load_inventory()

# (Añade este código debajo del anterior en main.py)


def get_gemini_response(query, df):
    """Genera una respuesta usando Gemini basado en la consulta y el inventario."""
    if df is None or df.empty:
        return "Lo siento, no pude cargar el inventario. Por favor, avisa a Gustavo."

    # Convertimos el DataFrame a un formato de texto simple para el prompt
    inventory_text = ""
    for index, row in df.iterrows():
        inventory_text += f"CAJA {row['CAJA']} - {row['ARTICULOS']}\n"

    # --- MODIFIED PROMPT ---
    prompt = f"""
    Eres un asistente de inventario doméstico llamado Mickey. Tu tarea es encontrar artículos en una lista y decir en qué caja están.
    Tu dueño se llama Gustavo. Responde siempre de forma amigable y directa.

    Este es el inventario completo:
    ---
    {inventory_text}
    ---

    Basado EXCLUSIVAMENTE en la lista de arriba, responde la siguiente pregunta.
    **Instrucciones importantes para tu búsqueda:**
    1. Lee la pregunta del usuario para identificar el artículo clave que está buscando.
    2. Revisa CUIDADOSAMENTE la lista de artículos de CADA caja.
    3. El artículo podría ser una sola palabra (ej. "bandeja") dentro de una descripción más larga (ej. "bandeja de madera para servir"). Debes encontrar estas coincidencias parciales.
    4. Si encuentras el artículo en una o más cajas, indica claramente en cuál o cuáles está.
    5. Si después de revisar todo no lo encuentras, dile amablemente que no lo encontraste.

    Pregunta: "{query}"

    Tu respuesta:
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error al llamar a la API de Gemini: {e}")
        return "Tuve un problema para pensar la respuesta. Inténtalo de nuevo."

    # (Añade este código al final de main.py)


# --- 2. COMANDOS DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un mensaje de bienvenida cuando el usuario escribe /start."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"¡Hola, {user_name}! Soy Mickey. Pregúntame dónde está guardado algo."
    )


async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recarga el inventario desde Google Sheets."""
    global inventory_df
    await update.message.reply_text("Recargando el inventario desde Google Sheets...")
    inventory_df = load_inventory()
    if inventory_df is not None:
        await update.message.reply_text("¡Listo! Inventario actualizado.")
    else:
        await update.message.reply_text("Hubo un error al recargar. Revisa la consola.")


# --- 3. MANEJO DE MENSAJES ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa el mensaje del usuario, lo envía a Gemini y responde."""
    user_query = update.message.text

    # Muestra un mensaje de "escribiendo..." para que el usuario sepa que está procesando
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Obtener la respuesta de Gemini
    response = get_gemini_response(user_query, inventory_df)

    # Enviar la respuesta
    await update.message.reply_text(response)


# --- 4. FUNCIÓN PRINCIPAL ---
def main() -> None:
    """Inicia el bot."""
    print("Iniciando bot...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Añadir los manejadores de comandos y mensajes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CommandHandler("reload", reload)
    )  # ¡Comando útil para actualizar!
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Iniciar el bot (polling)
    print("Bot iniciado y escuchando...")
    application.run_polling()


if __name__ == "__main__":
    main()
