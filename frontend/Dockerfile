# Заглушка до реализации Эпика 4 (клиентское приложение).
# nginx в prod резолвит upstream на старте, поэтому заглушка обязана
# реально слушать порт 3000, иначе контейнер nginx не поднимется.
FROM alpine:3.20

RUN printf 'Grasp frontend stub\n' > /index.html

CMD ["httpd", "-f", "-p", "3000", "-h", "/"]
