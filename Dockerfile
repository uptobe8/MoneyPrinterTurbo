FROM ghcr.io/harry0703/moneyprinterturbo:latest

WORKDIR /MoneyPrinterTurbo

RUN if [ ! -f config.toml ] && [ -f config.example.toml ]; then cp config.example.toml config.toml; fi

EXPOSE 8501

CMD ["streamlit", "run", "./webui/Main.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.enableCORS=true", "--browser.gatherUsageStats=false", "--client.toolbarMode=minimal", "--logger.hideWelcomeMessage=true", "--server.showEmailPrompt=false"]
