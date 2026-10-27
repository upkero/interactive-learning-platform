# Заглушка до реализации Эпика 3.5 (хост изолированных iframe-виджетов).
# В alpine:3.20 applet httpd отсутствует (вынесен в busybox-extras),
# поэтому используем busybox:1.36, где httpd есть в базовом комплекте.
# nginx в prod резолвит upstream на старте, поэтому заглушка обязана
# реально слушать порт 80, иначе контейнер nginx не поднимется.
# Раздаём только /www (индексную страницу), а не корень файловой системы.
FROM busybox:1.36

RUN mkdir -p /www && \
    printf '<!DOCTYPE html><html><body>Grasp widget-host stub</body></html>\n' > /www/index.html

CMD ["httpd", "-f", "-p", "80", "-h", "/www"]
