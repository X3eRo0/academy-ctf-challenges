#include "storage.h"

#include <sqlite3.h>
#include <string.h>
#include <stdlib.h>

struct Storage {
	sqlite3 *db;
};

static const char *SCHEMA_SQL =
	"PRAGMA foreign_keys=ON;"
	"CREATE TABLE IF NOT EXISTS users ("
	"  uid INTEGER PRIMARY KEY AUTOINCREMENT,"
	"  name TEXT NOT NULL UNIQUE,"
	"  balance INTEGER NOT NULL,"
	"  pass_plain TEXT NOT NULL"
	");"
	"CREATE TABLE IF NOT EXISTS flags ("
	"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
	"  uid INTEGER NOT NULL,"
	"  secret TEXT NOT NULL,"
	"  FOREIGN KEY(uid) REFERENCES users(uid) ON DELETE CASCADE"
	");"
	"CREATE TABLE IF NOT EXISTS listings ("
	"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
	"  fid INTEGER NOT NULL,"
	"  note TEXT NOT NULL,"
	"  sale_count INTEGER NOT NULL DEFAULT 0,"
	"  price INTEGER NOT NULL,"
	"  FOREIGN KEY(fid) REFERENCES flags(id) ON DELETE CASCADE"
	");";

static StorageResult map_sqlite_rc(int rc) {
	if (rc == SQLITE_OK || rc == SQLITE_DONE || rc == SQLITE_ROW) return STORAGE_OK;
	if (rc == SQLITE_CONSTRAINT) return STORAGE_CONFLICT;
	return STORAGE_ERR;
}

static StorageResult begin_tx(sqlite3 *db) {
	int rc = sqlite3_exec(db, "BEGIN IMMEDIATE TRANSACTION;", NULL, NULL, NULL);
	return rc == SQLITE_OK ? STORAGE_OK : STORAGE_ERR;
}

static StorageResult commit_tx(sqlite3 *db) {
	int rc = sqlite3_exec(db, "COMMIT;", NULL, NULL, NULL);
	return rc == SQLITE_OK ? STORAGE_OK : STORAGE_ERR;
}

static void rollback_tx(sqlite3 *db) {
	(void)sqlite3_exec(db, "ROLLBACK;", NULL, NULL, NULL);
}

StorageResult storage_open(const char *db_path, Storage **out_storage) {
	if (!db_path || !out_storage) return STORAGE_INVALID;
	Storage *s = (Storage *)calloc(1, sizeof(Storage));
	if (!s) return STORAGE_ERR;
	int rc = sqlite3_open(db_path, &s->db);
	if (rc != SQLITE_OK) {
		free(s);
		return STORAGE_ERR;
	}
	char *errmsg = NULL;
	rc = sqlite3_exec(s->db, SCHEMA_SQL, NULL, NULL, &errmsg);
	if (rc != SQLITE_OK) {
		sqlite3_free(errmsg);
		sqlite3_close(s->db);
		free(s);
		return STORAGE_ERR;
	}
	// Best-effort migration for earlier schema versions
	(void)sqlite3_exec(s->db, "ALTER TABLE users ADD COLUMN pass_plain TEXT;", NULL, NULL, NULL);
	*out_storage = s;
	return STORAGE_OK;
}

void storage_close(Storage *storage) {
	if (!storage) return;
	sqlite3_close(storage->db);
	free(storage);
}

StorageResult storage_user_create(Storage *storage, const char *name, User *out_user) {
	if (!storage || !name || !out_user) return STORAGE_INVALID;
	// Legacy create without password: set empty password
	const char *sql = "INSERT INTO users(name, balance, pass_plain) VALUES(?, 100, '');";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_text(stmt, 1, name, -1, SQLITE_TRANSIENT);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) {
		StorageResult r = map_sqlite_rc(rc);
		sqlite3_finalize(stmt);
		return r;
	}
	uint64_t uid = (uint64_t)sqlite3_last_insert_rowid(storage->db);
	sqlite3_finalize(stmt);
	User u = {0};
	u.uid = uid;
	strncpy(u.name, name, sizeof(u.name) - 1);
	u.balance = 100;
	*out_user = u;
	return STORAGE_OK;
}

StorageResult storage_user_get_by_id(Storage *storage, uint64_t uid, User *out_user) {
	if (!storage || !out_user) return STORAGE_INVALID;
	const char *sql = "SELECT uid, name, balance, pass_plain FROM users WHERE uid = ?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)uid);
	rc = sqlite3_step(stmt);
	if (rc == SQLITE_ROW) {
		User u = (User){0};
		u.uid = (uint64_t)sqlite3_column_int64(stmt, 0);
		const unsigned char *n = sqlite3_column_text(stmt, 1);
		if (n) strncpy(u.name, (const char *)n, sizeof(u.name) - 1);
		u.balance = (uint64_t)sqlite3_column_int64(stmt, 2);
		const unsigned char *p = sqlite3_column_text(stmt, 3);
		if (p) strncpy(u.password, (const char *)p, sizeof(u.password) - 1);
		*out_user = u;
		sqlite3_finalize(stmt);
		return STORAGE_OK;
	}
	sqlite3_finalize(stmt);
	return STORAGE_NOT_FOUND;
}

StorageResult storage_user_get_by_name(Storage *storage, const char *name, User *out_user) {
	if (!storage || !name || !out_user) return STORAGE_INVALID;
	const char *sql = "SELECT uid, name, balance, pass_plain FROM users WHERE name = ?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_text(stmt, 1, name, -1, SQLITE_TRANSIENT);
	rc = sqlite3_step(stmt);
	if (rc == SQLITE_ROW) {
		User u = (User){0};
		u.uid = (uint64_t)sqlite3_column_int64(stmt, 0);
		const unsigned char *n = sqlite3_column_text(stmt, 1);
		if (n) strncpy(u.name, (const char *)n, sizeof(u.name) - 1);
		u.balance = (uint64_t)sqlite3_column_int64(stmt, 2);
		const unsigned char *p = sqlite3_column_text(stmt, 3);
		if (p) strncpy(u.password, (const char *)p, sizeof(u.password) - 1);
		*out_user = u;
		sqlite3_finalize(stmt);
		return STORAGE_OK;
	}
	sqlite3_finalize(stmt);
	return STORAGE_NOT_FOUND;
}

StorageResult storage_flag_get_by_id(Storage *storage, uint64_t id, Flag *out_flag) {
	if (!storage || !out_flag) return STORAGE_INVALID;
	const char *sql = "SELECT id, uid, secret FROM flags WHERE id = ?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)id);
	rc = sqlite3_step(stmt);
	if (rc == SQLITE_ROW) {
		Flag f = {0};
		f.id = (uint64_t)sqlite3_column_int64(stmt, 0);
		f.uid = (uint64_t)sqlite3_column_int64(stmt, 1);
		const unsigned char *s = sqlite3_column_text(stmt, 2);
		if (s) strncpy(f.secret, (const char *)s, sizeof(f.secret) - 1);
		*out_flag = f;
		sqlite3_finalize(stmt);
		return STORAGE_OK;
	}
	sqlite3_finalize(stmt);
	return STORAGE_NOT_FOUND;
}

StorageResult storage_iter_flags_for_user(Storage *storage, uint64_t uid, flag_iter_cb cb, void *ctx) {
	if (!storage || !cb) return STORAGE_INVALID;
	const char *sql = "SELECT id, uid, secret FROM flags WHERE uid = ? ORDER BY id;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)uid);
	while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
		Flag f = {0};
		f.id = (uint64_t)sqlite3_column_int64(stmt, 0);
		f.uid = (uint64_t)sqlite3_column_int64(stmt, 1);
		const unsigned char *s = sqlite3_column_text(stmt, 2);
		if (s) strncpy(f.secret, (const char *)s, sizeof(f.secret) - 1);
		if (cb(&f, ctx)) break;
	}
	sqlite3_finalize(stmt);
	return STORAGE_OK;
}

StorageResult storage_listing_get_by_id(Storage *storage, uint64_t id, Listing *out_listing) {
	if (!storage || !out_listing) return STORAGE_INVALID;
	const char *sql = "SELECT id, fid, note, sale_count, price FROM listings WHERE id = ?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)id);
	rc = sqlite3_step(stmt);
	if (rc == SQLITE_ROW) {
		Listing l = {0};
		l.id = (uint64_t)sqlite3_column_int64(stmt, 0);
		l.fid = (uint64_t)sqlite3_column_int64(stmt, 1);
		const unsigned char *n = sqlite3_column_text(stmt, 2);
		if (n) strncpy(l.note, (const char *)n, sizeof(l.note) - 1);
		l.sale_count = (uint64_t)sqlite3_column_int64(stmt, 3);
		l.price = (uint64_t)sqlite3_column_int64(stmt, 4);
		*out_listing = l;
		sqlite3_finalize(stmt);
		return STORAGE_OK;
	}
	sqlite3_finalize(stmt);
	return STORAGE_NOT_FOUND;
}

StorageResult storage_iter_listings_for_user(Storage *storage, uint64_t uid, listing_iter_cb cb, void *ctx) {
	if (!storage || !cb) return STORAGE_INVALID;
	const char *sql =
		"SELECT l.id, l.fid, l.note, l.sale_count, l.price "
		"FROM listings l JOIN flags f ON l.fid = f.id WHERE f.uid = ? ORDER BY l.id;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)uid);
	while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
		Listing l = {0};
		l.id = (uint64_t)sqlite3_column_int64(stmt, 0);
		l.fid = (uint64_t)sqlite3_column_int64(stmt, 1);
		const unsigned char *n = sqlite3_column_text(stmt, 2);
		if (n) strncpy(l.note, (const char *)n, sizeof(l.note) - 1);
		l.sale_count = (uint64_t)sqlite3_column_int64(stmt, 3);
		l.price = (uint64_t)sqlite3_column_int64(stmt, 4);
		if (cb(&l, ctx)) break;
	}
	sqlite3_finalize(stmt);
	return STORAGE_OK;
}

// CRUD-style helpers
StorageResult storage_user_insert(Storage *storage, const User *user, User *out_user) {
	if (!storage || !user) return STORAGE_INVALID;
	const char *sql = "INSERT INTO users(name, balance, pass_plain) VALUES(?, ?, ?);";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_text(stmt, 1, user->name, -1, SQLITE_TRANSIENT);
	sqlite3_bind_int64(stmt, 2, (sqlite3_int64)user->balance);
	sqlite3_bind_text(stmt, 3, user->password, -1, SQLITE_TRANSIENT);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	uint64_t uid = (uint64_t)sqlite3_last_insert_rowid(storage->db);
	sqlite3_finalize(stmt);
	if (out_user) { *out_user = *user; ((User*)out_user)->uid = uid; }
	return STORAGE_OK;
}

StorageResult storage_user_update(Storage *storage, const User *user) {
	if (!storage || !user) return STORAGE_INVALID;
	const char *sql = "UPDATE users SET name=?, balance=?, pass_plain=? WHERE uid=?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_text(stmt, 1, user->name, -1, SQLITE_TRANSIENT);
	sqlite3_bind_int64(stmt, 2, (sqlite3_int64)user->balance);
	sqlite3_bind_text(stmt, 3, user->password, -1, SQLITE_TRANSIENT);
	sqlite3_bind_int64(stmt, 4, (sqlite3_int64)user->uid);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	sqlite3_finalize(stmt);
	return sqlite3_changes(storage->db) > 0 ? STORAGE_OK : STORAGE_NOT_FOUND;
}

StorageResult storage_user_delete_by_id(Storage *storage, uint64_t uid) {
	if (!storage) return STORAGE_INVALID;
	const char *sql = "DELETE FROM users WHERE uid=?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)uid);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	sqlite3_finalize(stmt);
	return sqlite3_changes(storage->db) > 0 ? STORAGE_OK : STORAGE_NOT_FOUND;
}

StorageResult storage_flag_insert(Storage *storage, const Flag *flag, Flag *out_flag) {
	if (!storage || !flag) return STORAGE_INVALID;
	const char *sql = "INSERT INTO flags(uid, secret) VALUES(?, ?);";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)flag->uid);
	sqlite3_bind_text(stmt, 2, flag->secret, -1, SQLITE_TRANSIENT);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	uint64_t id = (uint64_t)sqlite3_last_insert_rowid(storage->db);
	sqlite3_finalize(stmt);
	if (out_flag) { *out_flag = *flag; ((Flag*)out_flag)->id = id; }
	return STORAGE_OK;
}

StorageResult storage_flag_update(Storage *storage, const Flag *flag) {
	if (!storage || !flag) return STORAGE_INVALID;
	const char *sql = "UPDATE flags SET uid=?, secret=? WHERE id=?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)flag->uid);
	sqlite3_bind_text(stmt, 2, flag->secret, -1, SQLITE_TRANSIENT);
	sqlite3_bind_int64(stmt, 3, (sqlite3_int64)flag->id);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	sqlite3_finalize(stmt);
	return sqlite3_changes(storage->db) > 0 ? STORAGE_OK : STORAGE_NOT_FOUND;
}

StorageResult storage_flag_delete_by_id(Storage *storage, uint64_t id) {
	if (!storage) return STORAGE_INVALID;
	const char *sql = "DELETE FROM flags WHERE id=?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)id);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	sqlite3_finalize(stmt);
	return sqlite3_changes(storage->db) > 0 ? STORAGE_OK : STORAGE_NOT_FOUND;
}

StorageResult storage_listing_insert(Storage *storage, const Listing *listing, Listing *out_listing) {
	if (!storage || !listing) return STORAGE_INVALID;
	const char *sql = "INSERT INTO listings(fid, note, sale_count, price) VALUES(?, ?, ?, ?);";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)listing->fid);
	sqlite3_bind_text(stmt, 2, listing->note, -1, SQLITE_TRANSIENT);
	sqlite3_bind_int64(stmt, 3, (sqlite3_int64)listing->sale_count);
	sqlite3_bind_int64(stmt, 4, (sqlite3_int64)listing->price);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	uint64_t id = (uint64_t)sqlite3_last_insert_rowid(storage->db);
	sqlite3_finalize(stmt);
	if (out_listing) { *out_listing = *listing; ((Listing*)out_listing)->id = id; }
	return STORAGE_OK;
}

StorageResult storage_listing_update(Storage *storage, const Listing *listing) {
	if (!storage || !listing) return STORAGE_INVALID;
	const char *sql = "UPDATE listings SET fid=?, note=?, sale_count=?, price=? WHERE id=?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)listing->fid);
	sqlite3_bind_text(stmt, 2, listing->note, -1, SQLITE_TRANSIENT);
	sqlite3_bind_int64(stmt, 3, (sqlite3_int64)listing->sale_count);
	sqlite3_bind_int64(stmt, 4, (sqlite3_int64)listing->price);
	sqlite3_bind_int64(stmt, 5, (sqlite3_int64)listing->id);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	sqlite3_finalize(stmt);
	return sqlite3_changes(storage->db) > 0 ? STORAGE_OK : STORAGE_NOT_FOUND;
}

StorageResult storage_listing_delete_by_id(Storage *storage, uint64_t id) {
	if (!storage) return STORAGE_INVALID;
	const char *sql = "DELETE FROM listings WHERE id=?;";
	sqlite3_stmt *stmt = NULL;
	int rc = sqlite3_prepare_v2(storage->db, sql, -1, &stmt, NULL);
	if (rc != SQLITE_OK) return STORAGE_ERR;
	sqlite3_bind_int64(stmt, 1, (sqlite3_int64)id);
	rc = sqlite3_step(stmt);
	if (rc != SQLITE_DONE) { StorageResult r = map_sqlite_rc(rc); sqlite3_finalize(stmt); return r; }
	sqlite3_finalize(stmt);
	return sqlite3_changes(storage->db) > 0 ? STORAGE_OK : STORAGE_NOT_FOUND;
}

