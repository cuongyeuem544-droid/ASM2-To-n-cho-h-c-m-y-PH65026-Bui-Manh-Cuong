import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

// Đảm bảo an toàn khi chạy trên môi trường serverless (Vercel):
// Schema Prisma hiện tại sử dụng provider = "sqlite". Nếu biến DATABASE_URL trên Vercel
// vô tình bị cấu hình là PostgreSQL (Neon) hoặc bị trống, Prisma sẽ ném lỗi validate datasource
// lúc Next.js import route khi build. Cung cấp fallback URL SQLite an toàn.
const rawDbUrl = process.env.DATABASE_URL;
const sqliteUrl =
  rawDbUrl && rawDbUrl.startsWith("file:")
    ? rawDbUrl
    : "file:./dev.db";

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    datasources: {
      db: {
        url: sqliteUrl,
      },
    },
    log:
      process.env.NODE_ENV === "development"
        ? ["warn", "error"]
        : ["error"],
  });

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

export default prisma;
