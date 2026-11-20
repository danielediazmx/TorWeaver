FROM alpine:3.22
RUN apk add --no-cache tor curl && addgroup -S torweaver && adduser -S -G torweaver torweaver
COPY torrc /etc/tor/torrc
USER torweaver
ENTRYPOINT ["tor", "-f", "/etc/tor/torrc"]
