"""Gold-standard style example for DSA drafts.

This text is added to the Gemini prompts so every generated Java and Python
file follows the exact commenting style of the repository.
"""

JAVA_EXAMPLE = r'''
public class Solution {
    public boolean searchMatrix(int[][] matrix, int target) {
        // Brute Force Approach:
        // Iterate through every row and every column of the matrix to check if any element matches the target.
        // Time Complexity: O(m * n) where m is rows and n is columns.
        // Space Complexity: O(1).
        // Example matrix: [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], target = 3
        int bruteM = matrix.length; // bruteM = 3 (number of rows)
        int bruteN = matrix[0].length; // bruteN = 4 (number of columns)
        for (int i = 0; i < bruteM; i++) { // i = 0, 1, 2... checking each row
            for (int j = 0; j < bruteN; j++) { // j = 0, 1, 2, 3... checking each column
                if (matrix[i][j] == target) { // matrix[0][0] == 3 (1 == 3 -> false), matrix[0][1] == 3 (3 == 3 -> true)
                    return true; // returns true when match found
                }
            }
        }
        // return false; // returns false if loop completes without finding target

        // Optimal Approach:
        // Treat the 2D matrix as a virtual 1D sorted array of size m * n.
        // Time Complexity: O(log(m * n))
        // Space Complexity: O(1)

        // Example matrix: [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], target = 3
        int m = matrix.length;    // m = 3 (number of rows)
        int n = matrix[0].length; // n = 4 (number of columns)

        int l = 0;                // l = 0 (left pointer)
        int r = m * n - 1;        // r = 3 * 4 - 1 = 11 (right pointer)

        while (l <= r) {          // Condition: Iteration 1: 0 <= 11 (true) | Iteration 2: 0 <= 4 (true) | Iteration 3: 0 <= 1 (true) | Iteration 4: 1 <= 1 (true)
            int mid = l + (r - l) / 2;   // Iteration 1: mid = 5 | Iteration 2: mid = 2 | Iteration 3: mid = 0 | Iteration 4: mid = 1

            int row = mid / n;    // Iteration 1: row = 1 | Iteration 2: row = 0 | Iteration 3: row = 0 | Iteration 4: row = 0
            int col = mid % n;    // Iteration 1: col = 1 | Iteration 2: col = 2 | Iteration 3: col = 0 | Iteration 4: col = 1

            if (matrix[row][col] == target) {   // Iteration 1: matrix[1][1] == 3 (11 == 3 -> false) | Iteration 2: matrix[0][2] == 3 (5 == 3 -> false) | Iteration 3: matrix[0][0] == 3 (1 == 3 -> false) | Iteration 4: matrix[0][1] == 3 (3 == 3 -> true)
                return true;      // Iteration 4: returns true
            }

            else if (matrix[row][col] < target) {   // Iteration 1: matrix[1][1] < 3 (11 < 3 -> false) | Iteration 2: matrix[0][2] < 3 (5 < 3 -> false) | Iteration 3: matrix[0][0] < 3 (1 < 3 -> true)
                l = mid + 1;      // Iteration 3: l = 0 + 1 = 1
            }

            else {                // Iteration 1: taken (11 > 3) | Iteration 2: taken (5 > 3)
                r = mid - 1;      // Iteration 1: r = 5 - 1 = 4 | Iteration 2: r = 2 - 1 = 1
            }
        }
        return false;
    }
}
'''

PYTHON_EXAMPLE = r'''
class Solution:
    def searchMatrix(self, matrix, target):
        # Brute Force Approach:
        # Iterate through every row and every column of the matrix to check if any element matches the target.
        # Time Complexity: O(m * n) where m is rows and n is columns.
        # Space Complexity: O(1).
        # Example matrix: [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], target = 3
        brute_m = len(matrix)  # brute_m = 3 (number of rows)
        brute_n = len(matrix[0])  # brute_n = 4 (number of columns)
        for i in range(brute_m):  # i = 0, 1, 2... checking each row
            for j in range(brute_n):  # j = 0, 1, 2, 3... checking each column
                if matrix[i][j] == target:  # matrix[0][0] == 3 (1 == 3 -> False), matrix[0][1] == 3 (3 == 3 -> True)
                    return True  # returns True when match found
        # return False  # returns False if loop completes without finding target

        # Optimal Approach:
        # Treat the 2D matrix as a virtual 1D sorted array of size m * n.
        # Time Complexity: O(log(m * n))
        # Space Complexity: O(1)

        # Example matrix: [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], target = 3
        m = len(matrix)     # m = 3 (number of rows)
        n = len(matrix[0])  # n = 4 (number of columns)

        l = 0               # l = 0 (left pointer)
        r = m * n - 1       # r = 3 * 4 - 1 = 11 (right pointer)

        while l <= r:       # Condition: Iteration 1: 0 <= 11 (True) | Iteration 2: 0 <= 4 (True) | Iteration 3: 0 <= 1 (True) | Iteration 4: 1 <= 1 (True)
            mid = l + (r - l) // 2   # Iteration 1: mid = 5 | Iteration 2: mid = 2 | Iteration 3: mid = 0 | Iteration 4: mid = 1

            row = mid // n  # Iteration 1: row = 1 | Iteration 2: row = 0 | Iteration 3: row = 0 | Iteration 4: row = 0
            col = mid % n   # Iteration 1: col = 1 | Iteration 2: col = 2 | Iteration 3: col = 0 | Iteration 4: col = 1

            if matrix[row][col] == target:   # Iteration 1: matrix[1][1] == 3 (11 == 3 -> False) | Iteration 2: matrix[0][2] == 3 (5 == 3 -> False) | Iteration 3: matrix[0][0] == 3 (1 == 3 -> False) | Iteration 4: matrix[0][1] == 3 (3 == 3 -> True)
                return True  # Iteration 4: returns True

            elif matrix[row][col] < target:  # Iteration 1: matrix[1][1] < 3 (11 < 3 -> False) | Iteration 2: matrix[0][2] < 3 (5 < 3 -> False) | Iteration 3: matrix[0][0] < 3 (1 < 3 -> True)
                l = mid + 1  # Iteration 3: l = 0 + 1 = 1

            else:            # Iteration 1: taken (11 > 3) | Iteration 2: taken (5 > 3)
                r = mid - 1  # Iteration 1: r = 5 - 1 = 4 | Iteration 2: r = 2 - 1 = 1

        return False
'''

STYLE_BLOCK = (
    """
==================================================
EXACT CODE STYLE TO COPY (HIGHEST PRIORITY)
==================================================

Below is a real, finished example from the user's repository
(LeetCode 74, Search a 2D Matrix). Your Java and Python output MUST
look like this: same layout, same comment style, same level of detail.
If anything earlier in this prompt conflicts with this section,
THIS SECTION WINS.

THE RULES THIS EXAMPLE FOLLOWS (apply every one to the new problem):

1. ALL approaches live inside the SAME method, one after another,
   in this order: Brute Force first, then Better (only if it truly
   exists), then Optimal last.

2. Each approach starts with a comment block, in this order:
   - "Brute Force Approach:" / "Better Approach:" / "Optimal Approach:"
   - one or two plain lines explaining the idea
   - "Time Complexity: ..."
   - "Space Complexity: ..."
   - "Example ...: <the concrete input>" line

3. Choose ONE small concrete example for the current problem and use
   it in every dry-run comment of every approach. Copy the same
   "Example ..." line above each approach.

4. Variables of the brute-force approach get a "brute" prefix in Java
   (bruteM, bruteN) and "brute_" in Python (brute_m, brute_n), so they
   do not clash with the optimal approach's variables.

5. When an earlier approach would end with a final fall-through return
   that stops the method before the next approach runs, write that
   return as a COMMENTED-OUT line with a short explanation
   (see "// return false; // returns false if ...").
   A return inside a loop or condition stays active.

6. Every meaningful line has a trailing comment on the SAME line:
   - declarations: "// m = 3 (number of rows)"
   - pointers: "// r = 3 * 4 - 1 = 11 (right pointer)"
   - loops: "// i = 0, 1, 2... checking each row"
   - loop conditions: "// Condition: Iteration 1: 0 <= 11 (true) |
     Iteration 2: 0 <= 4 (true) | Iteration 3: ..."
   - computed values: "// Iteration 1: mid = 5 | Iteration 2: mid = 2 | ..."
   - if / else-if conditions: show the actual values and the result:
     "// Iteration 1: matrix[1][1] == 3 (11 == 3 -> false) | ..."
   - updates: "// Iteration 1: r = 5 - 1 = 4 | Iteration 2: r = 2 - 1 = 1"
   - else branch: "// Iteration 1: taken (11 > 3) | ..."
   Separate iterations with " | " on one line. Trace EVERY iteration
   until the algorithm ends for the example.

7. Align the trailing comments with spaces where several consecutive
   lines declare related values, as in the example.

8. Keep blank lines between logical blocks exactly as the example does.

9. Do not add generic comments like "// loop through array". Every
   comment shows real values from the example dry run.

10. SIMULATE the algorithm step by step on your chosen example before
    writing the comments. Every number in every comment must be
    correct. Never guess a value.

11. Python must use the same structure and the SAME wording in its
    comments (with # instead of //, True/False instead of true/false,
    // for integer division). It is NOT a shorter version of Java.

12. Code must be complete and runnable: the required class and method
    from the LeetCode signature, proper indentation, real newlines.

13. Do not copy this example's problem content. Copy only its STYLE and
    LAYOUT, applied to the problem you were asked about.

----- JAVA STYLE EXAMPLE START -----
""" + JAVA_EXAMPLE + """
----- JAVA STYLE EXAMPLE END -----

----- PYTHON STYLE EXAMPLE START -----
""" + PYTHON_EXAMPLE + """
----- PYTHON STYLE EXAMPLE END -----
"""
)