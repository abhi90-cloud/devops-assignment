FROM nginx:1.25-alpine

# Create directories
RUN mkdir -p /etc/nginx/ssl /var/log/nginx

# Copy configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Set permissions
RUN chown -R nginx:nginx /etc/nginx /var/log/nginx

EXPOSE 80 443

STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]
