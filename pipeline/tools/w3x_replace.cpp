#include "StormLib.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

static void usage(const char* a0) {
    std::cerr << "Usage:\n"
              << "  " << a0 << " extract <map> <archivePath> <outFile>\n"
              << "  " << a0 << " replace <map> <archivePath> <inFile>\n"
              << "  " << a0 << " list <map> [mask]\n";
}

static bool read_all(const char* path, std::vector<char>& out) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    f.seekg(0, std::ios::end);
    auto n = (std::streamoff)f.tellg();
    if (n < 0) return false;
    out.resize((size_t)n);
    f.seekg(0);
    if (n) f.read(out.data(), n);
    return true;
}

static bool write_all(const char* path, const void* data, size_t n) {
    std::ofstream f(path, std::ios::binary);
    if (!f) return false;
    if (n) f.write((const char*)data, (std::streamsize)n);
    return true;
}

int cmd_extract(const char* map, const char* arch, const char* outPath) {
    HANDLE hMpq = NULL;
    if (!SFileOpenArchive(map, 0, 0, &hMpq)) {
        std::cerr << "open archive failed: " << SErrGetLastError() << "\n";
        return 1;
    }
    HANDLE hFile = NULL;
    if (!SFileOpenFileEx(hMpq, arch, 0, &hFile)) {
        std::cerr << "open file failed: " << SErrGetLastError() << "\n";
        SFileCloseArchive(hMpq);
        return 1;
    }
    DWORD sz = SFileGetFileSize(hFile, NULL);
    std::vector<char> buf(sz ? sz : 1);
    DWORD got = 0;
    if (sz && !SFileReadFile(hFile, buf.data(), sz, &got, NULL)) {
        std::cerr << "read failed: " << SErrGetLastError() << "\n";
        SFileCloseFile(hFile);
        SFileCloseArchive(hMpq);
        return 1;
    }
    SFileCloseFile(hFile);
    SFileCloseArchive(hMpq);
    if (!write_all(outPath, buf.data(), got)) {
        std::cerr << "write out failed\n";
        return 1;
    }
    std::cout << "extracted " << got << " bytes -> " << outPath << "\n";
    return 0;
}

int cmd_replace(const char* map, const char* arch, const char* inPath) {
    std::vector<char> data;
    if (!read_all(inPath, data)) {
        std::cerr << "cannot read " << inPath << "\n";
        return 1;
    }
    HANDLE hMpq = NULL;
    if (!SFileOpenArchive(map, 0, 0, &hMpq)) {
        std::cerr << "open archive failed: " << SErrGetLastError() << "\n";
        return 1;
    }
    bool removed = SFileRemoveFile(hMpq, arch, 0);
    if (!removed) {
        std::cerr << "remove warn: " << SErrGetLastError() << " (will try REPLACEEXISTING)\n";
    }
    if (!SFileAddFileEx(hMpq, inPath, arch,
                        MPQ_FILE_COMPRESS | MPQ_FILE_REPLACEEXISTING,
                        MPQ_COMPRESSION_ZLIB, MPQ_COMPRESSION_NEXT_SAME)) {
        DWORD err1 = SErrGetLastError();
        std::cerr << "add zlib failed: " << err1 << "; retry uncompressed\n";
        if (!SFileAddFileEx(hMpq, inPath, arch, MPQ_FILE_REPLACEEXISTING, 0, 0)) {
            std::cerr << "add file failed: " << SErrGetLastError() << "\n";
            SFileCloseArchive(hMpq);
            return 1;
        }
    }
    // Do NOT compact — CompactArchive can corrupt WC3 maps for the game client.
    SFileCloseArchive(hMpq);
    std::cout << "replaced " << arch << " (" << data.size() << " bytes) in " << map << "\n";
    return 0;
}

int cmd_list(const char* map, const char* mask) {
    HANDLE hMpq = NULL;
    if (!SFileOpenArchive(map, 0, 0, &hMpq)) {
        std::cerr << "open archive failed: " << SErrGetLastError() << "\n";
        return 1;
    }
    SFILE_FIND_DATA fd;
    HANDLE hFind = SFileFindFirstFile(hMpq, mask, &fd, NULL);
    if (!hFind) {
        std::cerr << "find failed: " << SErrGetLastError() << "\n";
        SFileCloseArchive(hMpq);
        return 1;
    }
    int n = 0;
    do {
        std::cout << fd.cFileName << "\t" << fd.dwFileSize << "\n";
        ++n;
    } while (SFileFindNextFile(hFind, &fd));
    SFileFindClose(hFind);
    SFileCloseArchive(hMpq);
    std::cout << "total " << n << "\n";
    return 0;
}

int main(int argc, char** argv) {
    if (argc < 3) { usage(argv[0]); return 2; }
    std::string cmd = argv[1];
    if (cmd == "extract" && argc == 5) return cmd_extract(argv[2], argv[3], argv[4]);
    if (cmd == "replace" && argc == 5) return cmd_replace(argv[2], argv[3], argv[4]);
    if (cmd == "list" && (argc == 3 || argc == 4))
        return cmd_list(argv[2], argc == 4 ? argv[3] : "*");
    usage(argv[0]);
    return 2;
}
