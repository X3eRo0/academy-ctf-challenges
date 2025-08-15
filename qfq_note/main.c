#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <stddef.h>
#include <fcntl.h>

// Bug Type             Exp          Fix
// Race  Condition      [Medium]     [Hard]
// Not reset DEBUG var  [Easy]       [Easy]
// Heap  Overflow       [Medium]     [Easy]

#define container_of(ptr, type, member) \
    ((type*)((char*)(ptr) - offsetof(type, member)))
#define CRED_FILE "./flag"

struct list_head {
    struct list_head *next, *prev;
};

struct note {
    struct list_head list;
    char ctx[];
};

struct notes {
    size_t size;
    size_t sec_level;
    struct list_head note_list;
    struct list_head list;
};

unsigned char DEBUG = 1;
char creds[0x400];
struct list_head note_book;

long long int readNum(int fd)
{
    char buf[0x10] = {};
    read(fd, buf, sizeof(buf) - 1);
    return atoll(buf);
}
void panic(char* s)
{
    puts(s);
    exit(0);
}

static inline void list_add(struct list_head* new, struct list_head* head)
{
    new->next = head->next;
    new->prev = head;
    head->next->prev = new;
    head->next = new;
}

static inline void list_head_init(struct list_head* list)
{
    list->next = list;
    list->prev = list;
}

static inline int list_is_last(const struct list_head* list,
    const struct list_head* head)
{
    return list->next == head;
}

static inline void __list_del(struct list_head* prev, struct list_head* next)
{
    next->prev = prev;
    prev->next = next;
}

static inline void list_del(struct list_head* entry)
{
    __list_del(entry->prev, entry->next);
}

void do_send(int fd, char* msg)
{
    write(fd, msg, strlen(msg));
}

static inline struct notes* find_notes(size_t size, size_t sec_level)
{
    struct list_head* ptr = &note_book;
    while (ptr->next != &note_book) {
        ptr = ptr->next;
        struct notes* tmp_notes = container_of(ptr, struct notes, list);
        if (tmp_notes->size == size && tmp_notes->sec_level == sec_level)
            return tmp_notes;
    }
    return NULL;
}

struct notes* locate_notes(int fd, size_t* size, size_t* sec_level)
{
    do_send(fd, "Enter the size of note\n> ");
    *size = readNum(fd);
    if (*size > 0x1000 || (*size % 0x100))
        goto INVALID;
    do_send(fd, "Enter the Security Level of note\n> ");
    *sec_level = readNum(fd);
    if (*sec_level > 6)
        goto INVALID;
    return find_notes(*size, *sec_level);
INVALID:
    do_send(fd, "[X] INVALID\n");
    return NULL;
}

void add_note(int fd)
{
    size_t size, sec_level;
    struct notes* found = locate_notes(fd, &size, &sec_level);
    if (found == NULL) {
        struct notes* tmp = malloc(sizeof(struct notes));
        memset((char*)tmp, 0, sizeof(struct notes));
        if (tmp == 0) {
            do_send(fd, "[X] No more space\n");
            return;
        }
        tmp->size = size;
        tmp->sec_level = sec_level;
        list_add(&tmp->list, &note_book);
        list_head_init(&tmp->note_list);
        found = tmp;
    }
    struct note* note = malloc(size + sizeof(struct list_head));
    if (note == 0) {
        do_send(fd, "[X] No more space\n");
        return;
    }
    memset((char*)note, 0, size + sizeof(struct list_head));
    read(fd, note->ctx, size + sizeof(struct list_head)); // Bug 2. 0x10 bytes heap overflow
    list_add(&note->list, &found->note_list);
    return;
}

void del_note(int fd)
{
    size_t size, sec_level;
    struct notes* found = locate_notes(fd, &size, &sec_level);
    if (found == NULL) {
        do_send(fd, "[-] No note list found for such specs.\n");
        return;
    }
    do_send(fd, "Which page to delete:\n> ");
    size_t page_idx = readNum(fd);

    struct list_head* ptr = &found->note_list;
    size_t ct = 0;
    while (ptr->next != &found->note_list) {
        ptr = ptr->next;
        if (ct++ == page_idx) {
            list_del(ptr);
            free(container_of(ptr, struct note, list));

            if (list_is_last(&found->note_list, &found->note_list)) {
                list_del(&found->list);
                free(found);
            }
            return;
        }
    }
    return;
}

void show_note(int fd)
{
    size_t size, sec_level;
    struct notes* found = locate_notes(fd, &size, &sec_level);
    if (found == NULL) {
        do_send(fd, "[-] No note list found for such specs.\n");
        return;
    }
    do_send(fd, "Which page to read:\n> ");
    size_t page_idx = readNum(fd);

    struct list_head* ptr = &found->note_list;
    size_t ct = 0;
    while (ptr->next != &found->note_list) {
        ptr = ptr->next;
        if (ct++ == page_idx) {
            struct note* tmp = container_of(ptr, struct note, list);
            write(fd, tmp->ctx, size);
            return;
        }
    }
    return;
}

void edit_note(int fd)
{
    size_t size, sec_level;
    struct notes* found = locate_notes(fd, &size, &sec_level);
    if (found == NULL) {
        do_send(fd, "[-] No note list found for such specs.\n");
        return;
    }
    do_send(fd, "Which page to edit:\n> ");
    size_t page_idx = readNum(fd);

    struct list_head* ptr = &found->note_list;
    size_t ct = 0;
    while (ptr->next != &found->note_list) {
        ptr = ptr->next;
        if (ct++ == page_idx) {
            struct note* tmp = container_of(ptr, struct note, list);
            read(fd, tmp->ctx, size);
            return;
        }
    }
    return;
}

void playground(int conn_fd)
{
    while (1) {
        do_send(conn_fd, "[+] Notebook Manager\n");
        do_send(conn_fd, "[+] 1. Add a note\n");
        do_send(conn_fd, "[+] 2. Del a note\n");
        do_send(conn_fd, "[+] 3. Show a note\n");
        do_send(conn_fd, "[+] 4. Edit a note\n");
        int cmd = readNum(conn_fd);
        switch (cmd) {
        case 1:
            add_note(conn_fd);
            break;
        case 2:
            del_note(conn_fd);
            break;
        case 3:
            show_note(conn_fd);
            break;
        case 4:
            edit_note(conn_fd);
            break;
        default:
            return;
        }
    }
}

void* handle_client(void* arg)
{
    int conn_fd = *(int*)arg;
    free(arg); // Free malloc'ed socket fd
    char buf[0x400] = { 0 };
    do_send(conn_fd, "ADMIN role required, show me your cred:\n");
    read(conn_fd, buf, sizeof(buf));
    if (strlen(buf) >= 1 && buf[strlen(buf) - 1] == '\n')
        buf[strlen(buf) - 1] = 0;
    // Bug 0: Bypass-able strncmp, but we don't allow players to patch this
    // The expected patch is disabling the DEBUG
    if (strncmp(creds, buf, strlen(buf)))
        goto OUT;
    if (DEBUG == 1) {
        do_send(conn_fd, "[DEBUG] [Disable before the game]\n");
        do_send(conn_fd, "\t\tUser Input: ");
        do_send(conn_fd, buf);
        do_send(conn_fd, "\n");

        do_send(conn_fd, "\t\tExpected Input: ");
        do_send(conn_fd, creds);
        do_send(conn_fd, "\n");
    }

    playground(conn_fd);
OUT:
    close(conn_fd);
    return NULL;
}

void init()
{
    setvbuf(stdin, 0, 2, 0);
    setvbuf(stdout, 0, 2, 0);
    setvbuf(stderr, 0, 2, 0);
    int cred = open(CRED_FILE, 0);
    if (cred < 0)
        panic("Infra Issue: Report this issue to the game maintainer.");
    if (read(cred, creds, sizeof(creds) - 1) <= 0)
        panic("Infra Issue: Report this issue to the game maintainer.");
    close(cred);
    list_head_init(&note_book);
}

int main()
{
    init();

    int server_fd = -1;
    int start = 29000, end = 29999;
    int port;
    for (port = start; port <= end; port++) {
        server_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (server_fd < 0) {
            perror("socket");
            exit(1);
        }

        struct sockaddr_in addr = {
            .sin_family = AF_INET,
            .sin_port = htons(port),
            .sin_addr.s_addr = htonl(INADDR_ANY)
        };

        if (bind(server_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
            printf("[+] Listening on port %d\n", port);
            listen(server_fd, 16);
            break; // found usable port
        }

        close(server_fd);
        server_fd = -1;
    }
    if (server_fd == -1) {
        fprintf(stderr, "[-] No usable port found in range\n");
        exit(1);
    } else {
        printf("Current Notebook is running on port %d\n", port);
    }

    while (1) {
        struct sockaddr_in client;
        socklen_t len = sizeof(client);
        int* conn_fd = malloc(sizeof(int));
        *conn_fd = accept(server_fd, (struct sockaddr*)&client, &len);
        puts("[+] New connetction");
        pthread_t tid;
        pthread_create(&tid, NULL, handle_client, conn_fd);
        pthread_detach(tid); // Auto-reap thread
    }

    return 0;
}
