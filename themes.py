# Animal Companion Clock — Theme definitions
# Sprites are 240×240 native .bin files stored in the sprites/ directory.
# Palettes were auto-extracted when convert_sprites.py processed each image.

THEMES = {
    "kitten": {
        "name": "Luna",
        "bg_wake":       0xBDF7,   # Sky blue
        "bg_sleep":      0x10A2,   # Midnight navy
        "fg_wake":       0x0000,   # Black clock text
        "fg_sleep":      0xFFFF,   # White clock text
        "palette_wake": [
            0x969E, 0x969E, 0x969E, 0x969E,
            0x969E, 0x969E, 0x969E, 0x967E,
            0x967E, 0x85DA, 0x4A09, 0x10A3,
            0x967E, 0xB534, 0xD73C, 0x86BB,
        ],
        "palette_sleep": [
            0x0027, 0x0027, 0x0027, 0x0027,
            0x0025, 0x0004, 0x2965, 0x18E4,
            0x0884, 0x18C4, 0x2945, 0x9C91,
            0x18C9, 0x10C9, 0x10C9, 0x10C9,
        ],
        "sprite_wake":  "sprites/kitten_wake.bin",
        "sprite_sleep": "sprites/kitten_sleep.bin",
    },

    "dolphin": {
        "name": "Splash",
        "bg_wake":       0x03FF,   # Ocean cyan
        "bg_sleep":      0x000F,   # Midnight ocean
        "fg_wake":       0xFFFF,   # White clock text
        "fg_sleep":      0x07FF,   # Cyan clock text
        "palette_wake": [
            0x7FBE, 0x8FBE, 0xB7DF, 0xCFDF,
            0xFFFF, 0xFFFF, 0xE7FF, 0x6EFD,
            0x1A70, 0x663B, 0x14FA, 0x2F9F,
            0x071E, 0x171E, 0x06DE, 0x061D,
        ],
        "palette_sleep": [
            0x0043, 0x0044, 0x0002, 0x0022,
            0x22AD, 0x118A, 0x8F1C, 0x6536,
            0x0948, 0x08E7, 0x0064, 0x00A5,
            0x0928, 0x00E6, 0x00A5, 0x00A5,
        ],
        "sprite_wake":  "sprites/dolphin_wake.bin",
        "sprite_sleep": "sprites/dolphin_sleep.bin",
    },

    "chicken": {
        "name": "Peep",
        "bg_wake":       0x07E0,   # Farm green
        "bg_sleep":      0x2104,   # Night green
        "fg_wake":       0xFFFF,   # White clock text
        "fg_sleep":      0xFFE0,   # Yellow clock text
        "palette_wake": [
            0x4639, 0xE79C, 0x3DD6, 0x2862,
            0x3348, 0x2C69, 0xA925, 0xF526,
            0xAAE6, 0xFECA, 0x6D4A, 0x8665,
            0x8686, 0x8EA7, 0x7690, 0xFEEA,
        ],
        "palette_sleep": [
            0xFFBB, 0xFFDA, 0xFFBB, 0xFFBB,
            0xFFBB, 0xFFDB, 0xEE6F, 0x7328,
            0x0020, 0x0060, 0x0040, 0x0923,
            0x08C1, 0x0040, 0x1923, 0x4184,
        ],
        "sprite_wake":  "sprites/chicken_wake.bin",
        "sprite_sleep": "sprites/chicken_sleep.bin",
    },
}
