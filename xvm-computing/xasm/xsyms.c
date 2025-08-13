//
// Created by X3eRo0 on 3/3/2021.
//

#include "xasm.h"
#include <loader.h>

int main(int argc, char* argv[])
{

    // initialize binary structure
    xvm_bin* bin = init_xvm_bin();

    // argument checking
    if (argc != 2) {
        printf("Usage %s <xvm.bin>\n", argv[0]);
        fini_xvm_bin(bin);
        bin = NULL;
        return E_ERR;
    }

    xvm_bin_load_file(bin, argv[1]);
    if (bin->x_header->x_dbgsym) {
        show_symtab_info(bin->x_symtab);
    } else {
        xasm_warn("No symbols.\n");
    }
    fini_xvm_bin(bin);
    bin = NULL;

    return E_OK;
}
