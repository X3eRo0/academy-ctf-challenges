// Academy Bank - Storage API
// Abstracts persistence for users, flags, and listings

#ifndef ACADEMY_BANK_STORAGE_H
#define ACADEMY_BANK_STORAGE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>

// Tunable limits for fixed-size fields
#ifndef NAME_SZ
#define NAME_SZ 64
#endif

#ifndef FLAG_SZ
#define FLAG_SZ 256
#endif

#ifndef NOTE_SZ
#define NOTE_SZ 256
#endif

typedef struct {
	uint64_t uid;
	char name[NAME_SZ];
	uint64_t balance;
	char password[128];
} User;

typedef struct {
	uint64_t id;
	uint64_t uid;
	char secret[FLAG_SZ];
} Flag;

typedef struct {
	uint64_t id;
	uint64_t fid;
	char note[NOTE_SZ];
	uint64_t sale_count;
	uint64_t price;
} Listing;

// Opaque storage handle
typedef struct Storage Storage;

typedef enum {
	STORAGE_OK = 0,
	STORAGE_NOT_FOUND = 1,
	STORAGE_CONFLICT = 2,
	STORAGE_INVALID = 3,
	STORAGE_ERR = -1
} StorageResult;

// Iteration callbacks. Return non-zero from the callback to stop iteration early.
typedef int (*flag_iter_cb)(const Flag *flag, void *ctx);
typedef int (*listing_iter_cb)(const Listing *listing, void *ctx);

// Open/close
StorageResult storage_open(const char *db_path, Storage **out_storage);
void storage_close(Storage *storage);

// Users (CRUD)
StorageResult storage_user_get_by_id(Storage *storage, uint64_t uid, User *out_user);
StorageResult storage_user_get_by_name(Storage *storage, const char *name, User *out_user);

// CRUD-style operations
StorageResult storage_user_insert(Storage *storage, const User *user, User *out_user);
StorageResult storage_user_update(Storage *storage, const User *user);
StorageResult storage_user_delete_by_id(Storage *storage, uint64_t uid);

// Flags (CRUD)
StorageResult storage_flag_get_by_id(Storage *storage, uint64_t id, Flag *out_flag);
StorageResult storage_iter_flags_for_user(Storage *storage, uint64_t uid, flag_iter_cb cb, void *ctx);
StorageResult storage_flag_insert(Storage *storage, const Flag *flag, Flag *out_flag);
StorageResult storage_flag_update(Storage *storage, const Flag *flag);
StorageResult storage_flag_delete_by_id(Storage *storage, uint64_t id);

// Listings (CRUD)
StorageResult storage_listing_get_by_id(Storage *storage, uint64_t id, Listing *out_listing);
StorageResult storage_iter_listings_for_user(Storage *storage, uint64_t uid, listing_iter_cb cb, void *ctx);

// CRUD for listings
StorageResult storage_listing_insert(Storage *storage, const Listing *listing, Listing *out_listing);
StorageResult storage_listing_update(Storage *storage, const Listing *listing);
StorageResult storage_listing_delete_by_id(Storage *storage, uint64_t id);

#ifdef __cplusplus
}
#endif

#endif // ACADEMY_BANK_STORAGE_H

