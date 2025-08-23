CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Wpedantic -std=c11 -Wno-format-security
INC_DIR := include
SRC_DIR := src
BUILD_DIR := build

BIN := academy-bank

INCLUDES := -I$(INC_DIR)
LIBS := -lsqlite3
SRCS := $(SRC_DIR)/storage_sqlite.c $(SRC_DIR)/main.c
OBJS := $(SRCS:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)

all: $(BUILD_DIR)/$(BIN)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

$(BUILD_DIR)/$(BIN): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LIBS)

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all clean

