# Заглушка до реализации Эпика 3.5 (хост изолированных iframe-виджетов).
# nginx в prod резолвит upstream на старте, поэтому заглушка обязана
# реально слушать порт 80, иначе контейнер nginx не поднимется.
FROM alpine:3.20

RUN printf 'Grasp widget-host stub\n' > /index.html

CMD ["httpd", "-f", "-p", "80", "-h", "/"]
