// a function that reverses a given string
function reverseString(str) {
    return str.split('').reverse().join('');
}

// a function that sluggifies a string
function sluggify(str) {
    return str
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-');
}