FROM alpine:3.22
RUN apk add --no-cache tor curl && addgroup -S multitor && adduser -S -G multitor multitor
COPY torrc /etc/tor/torrc
USER multitor
ENTRYPOINT ["tor", "-f", "/etc/tor/torrc"]
