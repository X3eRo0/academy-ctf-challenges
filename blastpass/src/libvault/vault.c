#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <zlib.h>
#include <openssl/conf.h>
#include <openssl/evp.h>
#include <openssl/err.h>
#include <openssl/rand.h>
#include <openssl/sha.h>

#define SALT_SIZE 16
#define IV_SIZE 16
#define KEY_SIZE 32 // 256 bits for AES-256
#define PBKDF2_ITERATIONS 100000

int crypto_init()
{
    OpenSSL_add_all_algorithms();
    ERR_load_crypto_strings();
    return 0;
}

void crypto_cleanup()
{
    EVP_cleanup();
    ERR_free_strings();
}

int derive_key(const char* password, const unsigned char* salt, unsigned char* key)
{
    if (!PKCS5_PBKDF2_HMAC(password, strlen(password), salt, SALT_SIZE,
            PBKDF2_ITERATIONS, EVP_sha256(), KEY_SIZE, key)) {
        return -1;
    }
    return 0;
}

int compress_data(const unsigned char* data, size_t data_len,
    unsigned char** compressed, size_t* compressed_len)
{

    z_stream stream;
    stream.zalloc = Z_NULL;
    stream.zfree = Z_NULL;
    stream.opaque = Z_NULL;
    stream.avail_in = data_len;
    stream.next_in = (Bytef*)data;

    if (deflateInit2(&stream, Z_DEFAULT_COMPRESSION, Z_DEFLATED, 31, 8, Z_DEFAULT_STRATEGY) != Z_OK) {
        return -1;
    }

    *compressed_len = data_len + 64;
    *compressed = malloc(*compressed_len);
    if (!*compressed) {
        deflateEnd(&stream);
        return -1;
    }

    stream.avail_out = *compressed_len;
    stream.next_out = *compressed;

    int result = deflate(&stream, Z_FINISH);
    if (result != Z_STREAM_END) {
        free(*compressed);
        *compressed = NULL;
        deflateEnd(&stream);
        return -1;
    }

    *compressed_len = stream.total_out;
    deflateEnd(&stream);
    return 0;
}

int decompress_data(const unsigned char* compressed, size_t compressed_len,
    unsigned char** data, size_t* data_len)
{

    z_stream stream;
    stream.zalloc = Z_NULL;
    stream.zfree = Z_NULL;
    stream.opaque = Z_NULL;
    stream.avail_in = compressed_len;
    stream.next_in = (Bytef*)compressed;

    if (inflateInit2(&stream, 31) != Z_OK) {
        return -1;
    }

    size_t buffer_size = compressed_len * 4;
    *data = malloc(buffer_size);
    if (!*data) {
        inflateEnd(&stream);
        return -1;
    }

    stream.avail_out = buffer_size;
    stream.next_out = *data;

    int result = inflate(&stream, Z_FINISH);

    while (result == Z_BUF_ERROR) {
        size_t current_out = stream.total_out;
        buffer_size *= 2;
        *data = realloc(*data, buffer_size);
        if (!*data) {
            inflateEnd(&stream);
            return -1;
        }
        stream.next_out = *data + current_out;
        stream.avail_out = buffer_size - current_out;
        result = inflate(&stream, Z_FINISH);
    }

    if (result != Z_STREAM_END) {
        free(*data);
        *data = NULL;
        inflateEnd(&stream);
        return -1;
    }

    *data_len = stream.total_out;
    inflateEnd(&stream);
    return 0;
}

int encrypt_data(const unsigned char* plaintext, size_t plaintext_len,
    const unsigned char* key, const unsigned char* iv,
    unsigned char** ciphertext, size_t* ciphertext_len)
{

    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        return -1;
    }

    if (EVP_EncryptInit_ex(ctx, EVP_aes_256_ctr(), NULL, key, iv) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    *ciphertext_len = plaintext_len;
    *ciphertext = malloc(*ciphertext_len);
    if (!*ciphertext) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    int len;
    if (EVP_EncryptUpdate(ctx, *ciphertext, &len, plaintext, plaintext_len) != 1) {
        free(*ciphertext);
        *ciphertext = NULL;
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    int final_len;
    if (EVP_EncryptFinal_ex(ctx, *ciphertext + len, &final_len) != 1) {
        free(*ciphertext);
        *ciphertext = NULL;
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    *ciphertext_len = len + final_len;
    EVP_CIPHER_CTX_free(ctx);
    return 0;
}

int decrypt_data(const unsigned char* ciphertext, size_t ciphertext_len,
    const unsigned char* key, const unsigned char* iv,
    unsigned char** plaintext, size_t* plaintext_len)
{

    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        return -1;
    }

    if (EVP_DecryptInit_ex(ctx, EVP_aes_256_ctr(), NULL, key, iv) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    *plaintext = malloc(ciphertext_len);
    if (!*plaintext) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    int len;
    if (EVP_DecryptUpdate(ctx, *plaintext, &len, ciphertext, ciphertext_len) != 1) {
        free(*plaintext);
        *plaintext = NULL;
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    int final_len;
    if (EVP_DecryptFinal_ex(ctx, *plaintext + len, &final_len) != 1) {
        free(*plaintext);
        *plaintext = NULL;
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    *plaintext_len = len + final_len;
    EVP_CIPHER_CTX_free(ctx);
    return 0;
}

int vault_encrypt(const char* data, const char* password,
    unsigned char** output, size_t* output_len)
{

    unsigned char salt[SALT_SIZE], iv[IV_SIZE];
    if (RAND_bytes(salt, SALT_SIZE) != 1 || RAND_bytes(iv, IV_SIZE) != 1) {
        return -1;
    }

    unsigned char key[KEY_SIZE];
    if (derive_key(password, salt, key) != 0) {
        return -1;
    }

    unsigned char* compressed;
    size_t compressed_len;
    if (compress_data((unsigned char*)data, strlen(data), &compressed, &compressed_len) != 0) {
        return -1;
    }

    unsigned char* encrypted;
    size_t encrypted_len;
    if (encrypt_data(compressed, compressed_len, key, iv, &encrypted, &encrypted_len) != 0) {
        free(compressed);
        return -1;
    }

    *output_len = SALT_SIZE + IV_SIZE + encrypted_len;
    *output = malloc(*output_len);
    if (!*output) {
        free(compressed);
        free(encrypted);
        return -1;
    }

    memcpy(*output, salt, SALT_SIZE);
    memcpy(*output + SALT_SIZE, iv, IV_SIZE);
    memcpy(*output + SALT_SIZE + IV_SIZE, encrypted, encrypted_len);

    free(compressed);
    free(encrypted);
    return 0;
}

int vault_decrypt(const unsigned char* input, size_t input_len, const char* password,
    char** output, size_t* output_len)
{

    if (input_len < SALT_SIZE + IV_SIZE) {
        return -1;
    }

    const unsigned char* salt = input;
    const unsigned char* iv = input + SALT_SIZE;
    const unsigned char* encrypted = input + SALT_SIZE + IV_SIZE;
    size_t encrypted_len = input_len - SALT_SIZE - IV_SIZE;

    unsigned char key[KEY_SIZE];
    if (derive_key(password, salt, key) != 0) {
        return -1;
    }

    unsigned char* decrypted;
    size_t decrypted_len;
    if (decrypt_data(encrypted, encrypted_len, key, iv, &decrypted, &decrypted_len) != 0) {
        return -1;
    }

    unsigned char* decompressed;
    size_t decompressed_len;
    if (decompress_data(decrypted, decrypted_len, &decompressed, &decompressed_len) != 0) {
        free(decrypted);
        return -1;
    }

    *output = malloc(decompressed_len + 1);
    if (!*output) {
        free(decrypted);
        free(decompressed);
        return -1;
    }

    memcpy(*output, decompressed, decompressed_len);
    (*output)[decompressed_len] = '\0';
    *output_len = decompressed_len;

    free(decrypted);
    free(decompressed);
    return 0;
}

void crypto_free(void* ptr)
{
    if (ptr)
        free(ptr);
}

int execute_command(const char* command, char** output, char** error, int* return_code)
{
    if (!command || !output || !error || !return_code) {
        return -1;
    }

    *output = NULL;
    *error = NULL;
    *return_code = -1;

    // Create pipes for stdout and stderr
    FILE* fp = popen(command, "r");
    if (!fp) {
        return -1;
    }

    // Read output
    size_t output_size = 0;
    size_t output_capacity = 1024;
    *output = malloc(output_capacity);
    if (!*output) {
        pclose(fp);
        return -1;
    }

    char buffer[256];
    while (fgets(buffer, sizeof(buffer), fp) != NULL) {
        size_t buffer_len = strlen(buffer);
        
        // Resize output buffer if needed
        if (output_size + buffer_len + 1 > output_capacity) {
            output_capacity *= 2;
            char* new_output = realloc(*output, output_capacity);
            if (!new_output) {
                free(*output);
                *output = NULL;
                pclose(fp);
                return -1;
            }
            *output = new_output;
        }
        
        strcpy(*output + output_size, buffer);
        output_size += buffer_len;
    }

    // Null terminate
    if (*output) {
        (*output)[output_size] = '\0';
    }

    // Get return code
    *return_code = pclose(fp);
    if (*return_code == -1) {
        return -1;
    }

    // Convert wait status to exit code
    if (WIFEXITED(*return_code)) {
        *return_code = WEXITSTATUS(*return_code);
    } else {
        *return_code = -1;
    }

    // For simplicity, set error to empty string
    // (popen doesn't easily capture stderr separately)
    *error = malloc(1);
    if (*error) {
        (*error)[0] = '\0';
    }

    return 0;
}
