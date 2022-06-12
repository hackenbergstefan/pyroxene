// Server side C/C++ program to demonstrate Socket
// programming
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "gti2.h"

int gtisocket = 0;
int server_fd = 0;
uint8_t socket_buffer[16 * 1024] = { 0 };

static void socket_connect(void)
{

    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);

    if (gtisocket != 0)
    {
        close(gtisocket);
    }
    if (server_fd != 0)
    {
        shutdown(server_fd, SHUT_RDWR);
    }

    // Creating socket file descriptor
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0)
    {
        perror("socket failed");
        exit(EXIT_FAILURE);
    }

    // Forcefully attaching socket
    // if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt)))
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)))
    {
        perror("setsockopt");
        exit(EXIT_FAILURE);
    }
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1");
    address.sin_port = htons(1234);

    // Forcefully attaching socket
    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0)
    {
        perror("bind failed");
        exit(EXIT_FAILURE);
    }
    if (listen(server_fd, 1) < 0)
    {
        perror("listen");
        exit(EXIT_FAILURE);
    }

    if ((gtisocket = accept(server_fd, (struct sockaddr *)&address, (socklen_t *)&addrlen)) < 0)
    {
        perror("accept");
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char const *argv[])
{
    socket_connect();

    gti2_dispatcher();

    return 0;
}

void gti2_read(uint8_t *buffer, size_t length)
{
    ssize_t bytesread = read(gtisocket, &buffer[bytesread], length - bytesread);

    if (bytesread == 0)
    {
        // Socket was closed, reconnect
        socket_connect();
        ssize_t bytesread = read(gtisocket, &buffer[bytesread], length - bytesread);
    }
}

void gti2_write(uint8_t *buffer, size_t length)
{
    write(gtisocket, buffer, length);
}
