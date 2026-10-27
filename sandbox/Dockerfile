# Заглушка до реализации Эпика 3.5 (изолированная песочница виджетов).
# В alpine:3.20 applet httpd отсутствует (вынесен в busybox-extras),
# поэтому используем busybox:1.36, где httpd есть в базовом комплекте.
# Обязательно держим живой процесс, иначе с restart: unless-stopped
# контейнер зациклится на перезапусках в production-развёртывании.
# Раздаём только /www (индексную страницу), а не корень файловой системы.
FROM busybox:1.36

RUN mkdir -p /www && \
    printf '<!DOCTYPE html><html><body>Grasp sandbox stub</body></html>\n' > /www/index.html

CMD ["httpd", "-f", "-p", "8080", "-h", "/www"]
