# Заглушка до реализации Эпика 3.5 (изолированная песочница виджетов).
# Обязательно держим живой процесс, иначе с restart: unless-stopped
# контейнер зациклится на перезапусках в production-развёртывании.
FROM alpine:3.20

RUN printf 'Grasp sandbox stub\n' > /index.html

CMD ["httpd", "-f", "-p", "8080", "-h", "/"]
